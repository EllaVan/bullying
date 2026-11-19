#!/usr/bin/env python3
"""同一轨迹多次重跑 A3，统计方向一致率（可信度阶段1）。

基于 rerun_llm_from_trace：冻结原问答，仅 A3 走 LLM，重复 N 次后按
(turn_id, variable_id, unit_id) 聚合方向，输出一致率报告。

示例：
  cd psych_agent_v0.6.1
  python scripts/measure_a3_consistency.py --repeats 3 --max-turns 8
  python scripts/measure_a3_consistency.py --repeats 5 --output outputs/a3_consistency
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib.util

from psych_agent.a3_consistency import evidence_direction_rows, pairwise_agreement
from psych_agent.cli import run_dir
from psych_agent.dialogue_config import load_dialogue_config
from psych_agent.dialogue_runner import run_session
from psych_agent.io_utils import ValidationError, write_json
from psych_agent.measurement_controller import MeasurementController


def _load_rerun_helpers():
    path = ROOT / 'scripts' / 'rerun_llm_from_trace.py'
    spec = importlib.util.spec_from_file_location('rerun_llm_from_trace', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_rerun = _load_rerun_helpers()
DEFAULT_TRACE = _rerun.DEFAULT_TRACE
TraceAnswerProvider = _rerun.TraceAnswerProvider
build_agents = _rerun.build_agents
load_turns = _rerun.load_turns


def run_once(cfg, args, turns, plan_id, dest):
    controller = MeasurementController(
        cfg, plan_id, dest.name, max_total_turns=args.max_turns, synthetic=True)
    agents = build_agents(cfg, args, dest, turns)
    provider = TraceAnswerProvider(turns, verbose=not args.quiet)
    result = run_session(controller, agents, provider, dest,
                         on_scenario=(None if args.quiet else None))
    if result is None:
        raise ValidationError(f'会话未完成：{dest}')
    profile = json.loads((dest / 'profile.json').read_text(encoding='utf-8'))
    return evidence_direction_rows(profile), profile.get('coverage', {}).get('response_quality', {})


def main(argv=None):
    parser = argparse.ArgumentParser(description='轨迹多次 A3 方向一致率')
    parser.add_argument('--source', default=str(DEFAULT_TRACE))
    parser.add_argument('--plan', default=None)
    parser.add_argument('--llm-config', default='config/llm.local.json')
    parser.add_argument('--output', default=None)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--max-turns', type=int, default=8)
    parser.add_argument('--mode', choices=('frozen-qa', 'answers-only'), default='frozen-qa')
    parser.add_argument('--a1', choices=('template', 'llm'), default='template')
    parser.add_argument('--a5', choices=('template', 'llm'), default='template')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)

    if args.repeats < 2:
        raise SystemExit('--repeats 至少为 2')

    cfg = load_dialogue_config(ROOT)
    turns, plan_from_state = load_turns(Path(args.source))
    plan_id = args.plan or plan_from_state or 'full'
    if plan_id not in cfg.plans:
        raise SystemExit(f'未知计划：{plan_id}')

    try:
        root_dest = run_dir(ROOT, 'a3_consistency', args.output)
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc

    all_rows = []
    quality_rows = []
    for i in range(args.repeats):
        run_dest = root_dest / f'run_{i+1:02d}'
        run_dest.mkdir(parents=True, exist_ok=True)
        print(f'[{i+1}/{args.repeats}] → {run_dest}', flush=True)
        try:
            rows, quality = run_once(cfg, args, turns, plan_id, run_dest)
        except ValidationError as exc:
            print(f'运行 {i+1} 失败：{exc}', file=sys.stderr)
            return 2
        all_rows.append(rows)
        quality_rows.append(quality)
        write_json(run_dest / 'direction_snapshot.json', {
            'run': i + 1,
            'evidence_count': len(rows),
            'rows': [{'turn_id': r['key'][0], 'variable_id': r['key'][1],
                      'unit_id': r['key'][2], 'direction': r['direction'],
                      'rule_id': r['rule_id']} for r in rows],
            'response_quality': quality,
        })

    summary = pairwise_agreement(all_rows)
    report = {
        'schema_version': '0.6.1',
        'kind': 'a3_direction_consistency',
        'source': str(Path(args.source).resolve()),
        'plan_id': plan_id,
        'repeats': args.repeats,
        'max_turns': args.max_turns,
        'mode': args.mode,
        'agreement': {
            'keys': summary['keys'],
            'agree': summary['agree'],
            'rate': summary['rate'],
        },
        'per_key': summary['per_key'],
        'fallback_turns_by_run': [q.get('a3_fallback_turns') for q in quality_rows],
        'note': '文献定权见 docs/PSYCH_WEIGHT_THRESHOLDS.md；本报告只衡量 A3 方向稳定性，不是分数校准。',
    }
    write_json(root_dest / 'consistency_report.json', report)

    rate = summary['rate']
    rate_txt = 'n/a' if rate is None else f'{rate:.1%}'
    print(f'一致率：{rate_txt}（{summary["agree"]}/{summary["keys"]} 键稳定）')
    print(f'报告：{root_dest / "consistency_report.json"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
