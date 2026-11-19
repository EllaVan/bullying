#!/usr/bin/env python3
"""对已有 profile.json 按当前配置重算变量值、A4 与报告（无需 dialogue_state）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psych_agent.cli import run_dir
from psych_agent.dialogue_config import load_dialogue_config
from psych_agent.facets import summarize
from psych_agent.io_utils import ValidationError, write_json
from psych_agent.risk_engine import TestRiskScoringAgent, model_input
from psych_agent.risk_reporter import TemplateReportAgent, render_brief_report, render_report, validate_narrative


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile-file', required=True)
    parser.add_argument('--output', default=None)
    parser.add_argument('--compare-risk', default=None, help='旧 risk_result.json 用于打印对照')
    args = parser.parse_args(argv)

    cfg = load_dialogue_config(ROOT)
    profile = json.loads(Path(args.profile_file).read_text(encoding='utf-8'))
    ev = {e['evidence_id']: e for e in profile.get('evidence_ledger') or []}
    profile['conflict_resolutions'] = []
    for var in profile['variables']:
        facets, value, confidence = summarize(var['groups'], var['variable_id'], cfg, evidence_by_id=ev)
        var['facets'] = facets
        var['value'] = value
        var['confidence'] = confidence
        var['confidence_mode'] = 'engineering_facet_coverage_intensity'
        for facet in facets:
            if facet.get('conflict_audit'):
                profile['conflict_resolutions'].append({
                    'variable_id': var['variable_id'],
                    'facet_id': facet.get('facet_id'),
                    'facet_name': facet.get('name'),
                    **facet['conflict_audit'],
                })

    try:
        dest = run_dir(ROOT, 'recompute_scale', args.output)
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc

    write_json(dest / 'profile.json', profile)
    write_json(dest / 'risk_model_input.json', model_input(profile))
    risk = TestRiskScoringAgent(cfg).assess(profile)
    write_json(dest / 'risk_result.json', risk)
    narrative = validate_narrative(TemplateReportAgent().report(profile, risk), profile, risk)
    write_json(dest / 'report_narrative.json', narrative)
    (dest / 'report.md').write_text(render_report(profile, risk, narrative), encoding='utf-8')
    (dest / 'report_brief.md').write_text(render_brief_report(profile, risk, narrative), encoding='utf-8')

    print(f'输出：{dest}')
    print('anchor:', (risk.get('scale_constraints') or {}).get('anchor_package'))
    old = None
    if args.compare_risk:
        old = json.loads(Path(args.compare_risk).read_text(encoding='utf-8'))
    for i, row in enumerate(risk['roles']):
        prev = old['roles'][i] if old else None
        if prev:
            print(f"{row['role']:14} {row['score']} {row['level']:10} | was {prev['score']} {prev['level']}")
        else:
            print(f"{row['role']:14} {row['score']} {row['level']}")
        if row.get('gate_applied'):
            print('  gates:', [a['code'] for a in row['gate_applied'].get('actions') or []])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
