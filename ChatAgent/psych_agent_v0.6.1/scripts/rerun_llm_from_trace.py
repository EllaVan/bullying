#!/usr/bin/env python3
"""用既有真人会话的问答自动重跑多轮测评（学生回答不手输，A3 等走 LLM）。

默认冻结原问题文案，避免 A2 改题导致答非所问；A1 默认模板以加快复现，
A3/A5 可按需开 LLM。

示例：
  cd psych_agent_v0.6.1
  python scripts/rerun_llm_from_trace.py
  python scripts/rerun_llm_from_trace.py --max-turns 8
  # 省略 --output 时自动生成 outputs/YYYYMMDDTHHMMSS_llm_rerun_<id>/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psych_agent.agent_transport import JsonTransport
from psych_agent.cli import run_dir
from psych_agent.dialogue_config import load_dialogue_config
from psych_agent.dialogue_runner import Agents, run_session
from psych_agent.io_utils import ValidationError, read_json, write_json
from psych_agent.llm_client import inspect_settings
from psych_agent.measurement_controller import MeasurementController
from psych_agent.risk_engine import TestRiskScoringAgent
from psych_agent.risk_reporter import LLMReportAgent, TemplateReportAgent
from psych_agent.scenario_agent import LLMScenarioGenerator, TemplateScenarioGenerator
from psych_agent.turn_extractor import LLMTurnExtractor


DEFAULT_TRACE = ROOT / 'fixtures/real/20260914_69db8d61_trace.jsonl'


def load_turns(source: Path):
    """从 conversation_trace.jsonl、会话目录或 dialogue_state.json 读取轮次。"""
    source = source.resolve()
    if source.is_dir():
        trace = source / 'conversation_trace.jsonl'
        state = source / 'dialogue_state.json'
        if trace.is_file():
            source = trace
        elif state.is_file():
            source = state
        else:
            raise ValidationError(f'目录内找不到 conversation_trace.jsonl 或 dialogue_state.json：{source}')
    if source.suffix == '.jsonl':
        turns = []
        for line in source.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            turns.append(json.loads(line))
        return turns, None
    document = read_json(source)
    if isinstance(document, dict) and 'turns' in document:
        turns = [{'turn_id': t['turn_id'], 'question': t['question'], 'answer': t['answer'],
                  'target_unit_id': t.get('target_unit_id'), 'scenario_id': t.get('scenario_id'),
                  'condition_id': t.get('condition_id')} for t in document['turns']]
        return turns, document.get('plan_id')
    raise ValidationError(f'无法解析问答来源：{source}')


class TraceQuestionInterviewer:
    """按 turn_id 序号回放原问题，保证与原答对齐。"""

    def __init__(self, turns):
        self.turns = turns

    def ask(self, task, history):
        index = int(task['turn_id'][1:]) - 1
        if index < 0 or index >= len(self.turns):
            raise ValidationError(f'轨迹没有 {task["turn_id"]} 对应问题（轨迹共 {len(self.turns)} 轮）')
        question = self.turns[index].get('question')
        if not isinstance(question, str) or not question.strip():
            raise ValidationError(f'{task["turn_id"]} 缺少原问题文案')
        # 与 TemplateInterviewer / LLMInterviewer 一致：返回含 question 字段的对象
        return {'question': question.strip()}


class TraceAnswerProvider:
    def __init__(self, turns, verbose=True):
        self.turns = turns
        self.verbose = verbose
        self.used = 0

    def __call__(self, task, question):
        index = int(task['turn_id'][1:]) - 1
        if index < 0 or index >= len(self.turns):
            raise ValidationError(f'轨迹没有 {task["turn_id"]} 对应回答（轨迹共 {len(self.turns)} 轮）')
        row = self.turns[index]
        answer = row.get('answer')
        if not isinstance(answer, str) or not answer.strip():
            raise ValidationError(f'{task["turn_id"]} 缺少原回答')
        self.used += 1
        if self.verbose:
            preview = answer if len(answer) <= 60 else answer[:57] + '...'
            print(f'[{task["turn_id"]}] Q: {question[:50]}{"…" if len(question)>50 else ""}', flush=True)
            print(f'         A: {preview}', flush=True)
        return answer.strip()


def _transport(cfg, llm_config, role, dest):
    settings = read_json(llm_config if Path(llm_config).is_absolute() else cfg.root / llm_config)
    inspect_settings(settings)
    return JsonTransport(settings, role, dest / 'llm_calls')


def build_agents(cfg, args, dest, turns):
    transport = lambda role: _transport(cfg, args.llm_config, role, dest)
    if args.a1 == 'llm':
        a1 = LLMScenarioGenerator(cfg, transport('a1'))
    else:
        a1 = TemplateScenarioGenerator()
    if args.mode == 'frozen-qa':
        a2 = TraceQuestionInterviewer(turns)
    else:
        from psych_agent.interviewer import LLMInterviewer
        a2 = LLMInterviewer(cfg, transport('a2'))
    a3 = LLMTurnExtractor(cfg, transport('a3'))
    if args.a5 == 'llm':
        a5 = LLMReportAgent(cfg, transport('a5'))
    else:
        a5 = TemplateReportAgent()
    return Agents(a1, a2, a3, TestRiskScoringAgent(cfg), a5)


def main(argv=None):
    parser = argparse.ArgumentParser(description='基于既有真人问答轨迹自动重跑（LLM 抽取）')
    parser.add_argument('--source', default=str(DEFAULT_TRACE),
                        help='conversation_trace.jsonl / dialogue_state.json / 会话目录')
    parser.add_argument('--plan', default=None, help='访谈计划，默认 full 或来自 state')
    parser.add_argument('--llm-config', default='config/llm.local.json')
    parser.add_argument('--output', default=None,
                        help='输出目录；省略则按本地时间自动生成 outputs/YYYYMMDDTHHMMSS_llm_rerun_<id>/')
    parser.add_argument('--session-id', default=None)
    parser.add_argument('--max-turns', type=int, default=None, help='可选截断总轮数，便于冒烟')
    parser.add_argument('--mode', choices=('frozen-qa', 'answers-only'), default='frozen-qa',
                        help='frozen-qa=沿用原问题+原答；answers-only=A2 现场出题仅自动填答')
    parser.add_argument('--a1', choices=('template', 'llm'), default='template')
    parser.add_argument('--a5', choices=('template', 'llm'), default='template')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)

    cfg = load_dialogue_config(ROOT)
    turns, plan_from_state = load_turns(Path(args.source))
    plan_id = args.plan or plan_from_state or 'full'
    if plan_id not in cfg.plans:
        raise SystemExit(f'未知计划：{plan_id}')

    try:
        dest = run_dir(ROOT, 'llm_rerun', args.output)
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc
    session_id = args.session_id or dest.name

    # 标记 synthetic：回答来自真人轨迹，但 A3 为本次重抽取
    controller = MeasurementController(cfg, plan_id, session_id, max_total_turns=args.max_turns, synthetic=True)
    agents = build_agents(cfg, args, dest, turns)
    provider = TraceAnswerProvider(turns, verbose=not args.quiet)

    meta = {
        'schema_version': '0.6.1',
        'kind': 'llm_rerun_from_trace',
        'source': str(Path(args.source).resolve()),
        'plan_id': plan_id,
        'mode': args.mode,
        'a1': args.a1,
        'a5': args.a5,
        'trace_turns': len(turns),
        'session_id': session_id,
        'note': '学生问答来自既有轨迹；A3（及可选 A1/A2/A5）为本次 LLM 调用。synthetic=true 表示非现场手输会话。',
    }
    write_json(dest / 'rerun_manifest.json', meta)

    print(f'开始轨迹重跑：plan={plan_id} mode={args.mode} trace={len(turns)}轮 → {dest}', flush=True)
    try:
        result = run_session(
            controller, agents, provider, dest,
            on_scenario=(None if args.quiet else (lambda s: print('\n情境：' + s['text'][:120], flush=True))),
        )
    except ValidationError as exc:
        print(f'失败：{exc}', file=sys.stderr)
        return 2

    if result is None:
        print(f'已暂停。状态：{dest / "dialogue_state.json"}')
        return 1

    done = len(controller.snapshot()['turns'])
    print(f'完成 {done} 轮；使用轨迹回答 {provider.used} 条。')
    print(f'完整报告：{dest / "report.md"}')
    print(f'简洁报告：{dest / "report_brief.md"}')
    print(f'输出目录：{dest}')
    if done < len(turns):
        print(f'注意：计划在 {done} 轮结束，轨迹尚余 {len(turns) - done} 条未用（可能因 max-turns 或计划覆盖提前完成）。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
