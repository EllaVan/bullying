"""回答冲突消解：保留全部证据，按参照框架优先级与强度软计分，不因冲突丢弃 facet。

0.5.2 问题：同 facet 冲突时 value=None 退出分母，剩余单面易极端。

0.6.1 终版策略：
1. 全部证据保留；conflict_audit 写明 cause、两侧 quote/轮次/框架；
2. 分类：same_group_bidirectional / cross_frame / cross_scenario / cross_context；
3. 消解为单一值后以满分权重计入风险分（不因冲突放松计分）；
4. 不确定性只进入工程置信标签（confidence_tag=conflict）。
"""
from copy import deepcopy

FRAME_PRIORITY = {
    'real_event_self_report': 5,
    'habitual_self_report': 4,
    'task_performance': 3,
    'general_belief': 2,
    'hypothetical_intent': 1,
    'unclear': 0,
}

# 未显式给出 intensity 时的回退表；优先使用 variable_scoring.frame_default_intensity（INT-1）。
DEFAULT_INTENSITY = {
    'real_event_self_report': 5,
    'habitual_self_report': 4,
    'task_performance': 3,
    'general_belief': 2,
    'hypothetical_intent': 1,
    'unclear': 1,
}


def _frame_intensity_table(scoring):
    table = scoring.get('frame_default_intensity') if isinstance(scoring, dict) else None
    return table if isinstance(table, dict) and table else DEFAULT_INTENSITY


def _clamp01(value):
    return max(0.0, min(1.0, value))


def intensity_to_support(direction, intensity, scoring):
    """将方向 + Likert 强度映射到变量值 0–1。

    higher + 5 → 接近 1；lower + 5 → 接近 0；强度越弱越靠近中性。
    """
    require_intensity = scoring.get('intensity_scale', {})
    lo = require_intensity.get('min', 1)
    hi = require_intensity.get('max', 5)
    if intensity is None:
        intensity = require_intensity.get('default_when_missing', 3)
    intensity = max(lo, min(hi, int(intensity)))
    # (i - min) / (max - min) ∈ [0,1]
    strength = (intensity - lo) / max(1, hi - lo)
    neutral = scoring.get('direction_values', {}).get('mixed', 0.5)
    if direction == 'higher':
        # 弱 higher 略高于中性，强 higher 接近 1
        return _clamp01(neutral + (1.0 - neutral) * strength)
    if direction == 'lower':
        return _clamp01(neutral - neutral * strength)
    return None


def _observation_rows(groups, evidence_by_id, scoring):
    rows = []
    for group in groups:
        frame = group.get('reference_frame', 'unclear')
        for evidence_id in group.get('evidence_ids', []):
            evidence = evidence_by_id.get(evidence_id)
            direction = None
            intensity = None
            if evidence:
                direction = evidence.get('direction')
                intensity = evidence.get('intensity')
                frame = evidence.get('reference_frame') or frame
            if direction in (None, 'unclear'):
                # 回退到组方向集合中的明确项（组级可能已汇总）
                continue
            if intensity is None:
                intensity = _frame_intensity_table(scoring).get(
                    frame, scoring.get('intensity_scale', {}).get('default_when_missing', 3))
            support = intensity_to_support(direction, intensity, scoring)
            if support is None:
                continue
            rows.append({
                'evidence_id': evidence_id,
                'group_id': group.get('group_id'),
                'direction': direction,
                'intensity': intensity,
                'support': support,
                'reference_frame': frame,
                'frame_priority': FRAME_PRIORITY.get(frame, 0),
                'scenario_ids': tuple(group.get('scenario_ids') or []),
                'condition_id': group.get('condition_id'),
                'unit_id': group.get('unit_id'),
                'turn_hint': group.get('observation_ids', [None])[0],
            })
        # 若组有方向但证据未挂上（结构缺口），仍用组方向兜底
        directions = {d for d in group.get('directions', []) if d != 'unclear'}
        if directions and not any(r['group_id'] == group.get('group_id') for r in rows):
            for direction in directions:
                intensity = _frame_intensity_table(scoring).get(frame, 3)
                support = intensity_to_support(direction, intensity, scoring)
                rows.append({
                    'evidence_id': None,
                    'group_id': group.get('group_id'),
                    'direction': direction,
                    'intensity': intensity,
                    'support': support,
                    'reference_frame': frame,
                    'frame_priority': FRAME_PRIORITY.get(frame, 0),
                    'scenario_ids': tuple(group.get('scenario_ids') or []),
                    'condition_id': group.get('condition_id'),
                    'unit_id': group.get('unit_id'),
                    'turn_hint': group.get('observation_ids', [None])[0],
                })
    return rows


CONFLICT_CAUSE = {
    'same_group_bidirectional': '同一观察组内同时抽出相反方向（多为同句双命中、表述含糊或规则误触）',
    'cross_frame': '不同参照框架下方向不一致（如假设意向 vs 真实/习惯自述）',
    'cross_scenario': '不同情境下方向不一致（跨场景语境差）',
    'cross_context': '同框架、同情境下多处回答方向不一致（前后表述对冲或澄清后改口）',
}

RESOLUTION_CAUSE = {
    'soft_midpoint_same_group': '同组双向取软中点合成一个计分值',
    'prefer_higher_frame': '优先采信更高参照框架一侧（真实经历>习惯>任务>信念>假设）',
    'frame_weighted_soft_mean': '按参照框架优先级对两侧 support 加权平均',
}


def classify_conflict(rows):
    directions = {r['direction'] for r in rows}
    if len(directions) <= 1:
        return None
    same_group = len({r['group_id'] for r in rows}) == 1
    frames = {r['reference_frame'] for r in rows}
    scenarios = {s for r in rows for s in r['scenario_ids']}
    if same_group:
        return 'same_group_bidirectional'
    if len(frames) > 1:
        return 'cross_frame'
    if len(scenarios) > 1:
        return 'cross_scenario'
    return 'cross_context'


def resolve_facet(groups, variable_id, facet_spec, cfg, evidence_by_id=None):
    """返回 facet 行（含冲突审计）以及用于聚合的计分值。"""
    scoring = cfg.variable_scoring
    policy = scoring.get('conflict_policy', {})
    evidence_by_id = evidence_by_id or {}
    rows = _observation_rows(groups, evidence_by_id, scoring)
    evidence_ids = sorted({e for g in groups for e in g.get('evidence_ids', [])})
    base = {
        **facet_spec,
        'group_ids': [g['group_id'] for g in groups],
        'source_item_ids': sorted({i for g in groups for i in g.get('source_item_ids', [])}),
        'evidence_ids': evidence_ids,
        'reference_frames': sorted({g['reference_frame'] for g in groups}),
        'conflict_audit': None,
    }
    if not groups:
        return {**base, 'status': 'unknown', 'value': None, 'score_weight_factor': 0.0}
    directions = {d for g in groups for d in g.get('directions', []) if d != 'unclear'}
    if not directions and not rows:
        return {**base, 'status': 'descriptive_only', 'value': None, 'score_weight_factor': 0.0}
    if not rows:
        # 仅有组方向
        if len(directions) == 1:
            direction = next(iter(directions))
            frames = [g.get('reference_frame', 'unclear') for g in groups]
            table = _frame_intensity_table(scoring)
            intensity = max(table.get(f, 3) for f in frames) if frames else 3
            value = intensity_to_support(direction, intensity, scoring)
            return {**base, 'status': 'observed', 'value': round(value, 4), 'score_weight_factor': 1.0}
        directions = directions  # fall through with synthetic rows below

    conflict_type = classify_conflict(rows) if rows else ('cross_context' if len(directions) > 1 else None)

    if conflict_type is None:
        # 单方向：按框架权重 × support 加权
        total_w = sum(max(1, r['frame_priority']) for r in rows) or 1
        value = sum(r['support'] * max(1, r['frame_priority']) for r in rows) / total_w
        return {**base, 'status': 'observed', 'value': round(value, 4), 'score_weight_factor': 1.0}

    # —— 冲突消解 ——
    mode = policy.get('resolution', 'frame_weighted_soft_mean')
    conflict_weight = float(policy.get('conflict_weight_factor', 1.0))
    same_group_weight = float(policy.get('same_group_bidirectional_weight_factor', 1.0))
    prefer_frame = bool(policy.get('prefer_higher_frame', True))

    if conflict_type == 'same_group_bidirectional':
        # 同组双向：软中点得到单一计分值；默认满分权重计入（不因冲突放松严格性）
        value = sum(r['support'] for r in rows) / len(rows)
        weight_factor = same_group_weight
        method = 'soft_midpoint_same_group'
    elif mode == 'prefer_higher_frame' or prefer_frame:
        max_p = max(r['frame_priority'] for r in rows)
        top = [r for r in rows if r['frame_priority'] == max_p]
        top_dirs = {r['direction'] for r in top}
        if len(top_dirs) == 1:
            value = sum(r['support'] for r in top) / len(top)
            method = 'prefer_higher_frame'
            weight_factor = conflict_weight
        else:
            # 最高优先级框架内部仍冲突 → 框架加权均值
            total_w = sum(max(1, r['frame_priority']) for r in rows) or 1
            value = sum(r['support'] * max(1, r['frame_priority']) for r in rows) / total_w
            method = 'frame_weighted_soft_mean'
            weight_factor = conflict_weight
    else:
        total_w = sum(max(1, r['frame_priority']) for r in rows) or 1
        value = sum(r['support'] * max(1, r['frame_priority']) for r in rows) / total_w
        method = 'frame_weighted_soft_mean'
        weight_factor = conflict_weight

    cause = CONFLICT_CAUSE.get(conflict_type, conflict_type)
    resolution_cause = RESOLUTION_CAUSE.get(method, method)
    audit = {
        'conflict_type': conflict_type,
        'cause': cause,
        'resolution_method': method,
        'resolution_cause': resolution_cause,
        'resolved_value': round(value, 4),
        'score_weight_factor': weight_factor,
        'sides': [
            {
                'direction': r['direction'],
                'support': round(r['support'], 4),
                'intensity': r['intensity'],
                'reference_frame': r['reference_frame'],
                'evidence_id': r['evidence_id'],
                'group_id': r['group_id'],
                'scenario_ids': list(r['scenario_ids']),
                'quote': (evidence_by_id.get(r['evidence_id']) or {}).get('quote') if r.get('evidence_id') else None,
                'turn_id': (evidence_by_id.get(r['evidence_id']) or {}).get('turn_id') if r.get('evidence_id') else None,
                'source_item_ids': list((evidence_by_id.get(r['evidence_id']) or {}).get('source_item_ids') or []),
            }
            for r in rows
        ],
        'policy_note': '冲突须写明原因；消解后的值以配置权重严格计入风险分（默认权重因子=1），不确定性只进入工程置信标签，不因冲突放松分数计算。',
    }
    return {
        **base,
        'status': 'resolved_conflict',
        'value': round(value, 4),
        'score_weight_factor': weight_factor,
        'conflict_audit': audit,
    }


def summarize_with_conflicts(groups, variable_id, cfg, evidence_by_id=None):
    """替代 facets.summarize：冲突可计分，权重乘 score_weight_factor。"""
    rows = []
    definitions = cfg.facet_config['variables'][variable_id]
    for spec in definitions:
        selected = [g for g in groups if g['unit_id'] in spec['unit_ids']]
        row = resolve_facet(selected, variable_id, spec, cfg, evidence_by_id=evidence_by_id)
        rows.append(row)
    available = [r for r in rows if r['value'] is not None and r['weight'] > 0]
    # 有效权重 = 配置权重 × score_weight_factor（终版冲突默认因子=1.0）
    weighted = [(r['value'], r['weight'] * r.get('score_weight_factor', 1.0)) for r in available]
    total = sum(w for _, w in weighted)
    value = round(sum(v * w for v, w in weighted) / total, 4) if total else None
    expected = sum(r['weight'] for r in rows)
    confidence = round(total / expected, 4) if expected else 0.0
    return rows, value, confidence
