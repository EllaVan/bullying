"""量表构念约束：在 A4 加权分之后做门控/封顶，不改变问答流程。

锚定包 olweus_dbvs_bpbq_v1 规则见 docs/SCALE_RULES_SOURCE.md。
"""
from copy import deepcopy

from .risk_engine import level_for


def _frame_mix(profile, role_variable_ids):
    frames = []
    for var in profile['variables']:
        if var['variable_id'] not in role_variable_ids:
            continue
        for g in var.get('groups') or []:
            frames.append(g.get('reference_frame'))
    if not frames:
        return {'hypothetical_only': False, 'has_real_or_habit': False, 'n': 0,
                'hypo_fraction': 0.0}
    hypo = sum(1 for f in frames if f == 'hypothetical_intent')
    realish = sum(1 for f in frames if f in ('real_event_self_report', 'habitual_self_report'))
    return {
        'hypothetical_only': hypo == len(frames),
        'has_real_or_habit': realish > 0,
        'n': len(frames),
        'hypo_fraction': hypo / len(frames),
    }


def _experience_roles(profile):
    exp = profile.get('experience') or {}
    return {e.get('role') for e in exp.get('events') or [] if e.get('role') and e.get('role') != 'unknown'}


def _cap(score, cap, notes, code, detail):
    if score > cap:
        notes.append({'code': code, 'detail': detail})
        return float(cap)
    return score


def apply_scale_constraints(result, profile, constraints):
    """就地更新 roles 的 score/level，并写入 gate_applied 审计。"""
    if not constraints or not constraints.get('enabled', True):
        result['scale_constraints'] = {'enabled': False, 'gates': []}
        return result

    role_vars = {role: [s['variable_id'] for s in result['scoring_policy']['roles'][role]]
                 for role in (r['role'] for r in result['roles'])}
    hypo_cfg = constraints.get('hypothesis_discount') or {}
    gates_cfg = constraints.get('bullying_construct_gates') or {}
    dig = int(result['scoring_policy'].get('score_round_digits', 2))
    applied = []
    role_map = {'bully': 'perpetrator', 'victim': 'victim', 'bystander': 'observer',
                'bully_victim': 'victim'}

    for row in result['roles']:
        role = row['role']
        if row['score'] is None:
            row['gate_applied'] = None
            continue
        original = row['score']
        notes = []
        score = float(original)
        mix = _frame_mix(profile, set(role_vars.get(role, [])))
        exp_roles = _experience_roles(profile)
        gate = gates_cfg.get(role) or {}
        high_cut = row['thresholds'][1]

        # OLV-2：假设意向占比高 → 封顶
        if hypo_cfg.get('enabled', True) and mix['n'] and mix.get('hypo_fraction', 0) >= hypo_cfg.get('min_hypo_fraction', 0.85):
            caps = hypo_cfg.get('score_cap_by_role') or {}
            if role in caps:
                score = _cap(score, float(caps[role]), notes, 'hypothesis_score_cap',
                             f'OLV-2：假设意向占比高，分数封顶至{caps[role]}')

        # OLV-1 / BPB-3：高等级需要真实/习惯或经历台账
        need_real = gate.get('high_requires_real_or_habit', False)
        exp_role = role_map.get(role)
        exp_ok = mix['has_real_or_habit'] or exp_role in exp_roles
        if role == 'bully_victim':
            # 施暴侧：perpetrator 经历或任意 real/habit 帧
            bully_side = mix['has_real_or_habit'] or 'perpetrator' in exp_roles
            victim_side = 'victim' in exp_roles or mix['has_real_or_habit']
            exp_ok = bully_side  # 无真实/习惯且无施暴经历时先挡高档
        if need_real and score >= high_cut and not exp_ok:
            cap = gate.get('cap_without_real_or_habit', high_cut - 0.01)
            score = _cap(score, float(cap), notes, 'high_needs_real_or_habit',
                         'OLV-1：无真实经历/习惯自述支撑时，不允许进入重点关注')

        # OLV-3：受害经历
        if role in ('victim', 'bully_victim') and gate.get('high_requires_victim_experience', False):
            if 'victim' not in exp_roles and score >= high_cut:
                cap = gate.get('cap_without_victim_experience', high_cut - 0.01)
                score = _cap(score, float(cap), notes, 'high_needs_victim_experience',
                             'OLV-3：无本人受害经历记录时，受害相关重点关注封顶')

        # OLV-3：双角色需两侧卷入（施暴侧 + 受害侧）
        if role == 'bully_victim' and gate.get('high_requires_dual_involvement', False):
            bully_side = mix['has_real_or_habit'] or 'perpetrator' in exp_roles
            victim_side = 'victim' in exp_roles
            if score >= high_cut and not (bully_side and victim_side):
                # 无双侧真实卷入时，即使未到 high 也可能偏高 → 用 dual cap
                cap = gate.get('cap_without_dual_involvement', 59.99)
                if score > float(cap):
                    score = _cap(score, float(cap), notes, 'high_needs_dual_involvement',
                                 'OLV-3：兼有角色需施暴侧与受害侧卷入证据，否则封顶')

        score = round(score, dig)
        row['score'] = score
        row['level'] = level_for(score, row['thresholds'])
        gate_note = None
        if notes or score != original:
            gate_note = {'from_score': original, 'to_score': score, 'actions': notes,
                         'frame_mix': mix, 'experience_roles': sorted(exp_roles),
                         'rule_ids': list(gate.get('rule_ids') or [])}
        row['gate_applied'] = gate_note
        if gate_note:
            applied.append({'role': role, **deepcopy(gate_note)})

    form_policy = constraints.get('form_policy') or {}
    result['scale_constraints'] = {
        'enabled': True,
        'config_id': constraints.get('config_id', 'scale_constraints'),
        'anchor_package': constraints.get('anchor_package'),
        'source_doc': constraints.get('source_doc'),
        'gates': applied,
        'form_policy': form_policy,
        'note': constraints.get('note', ''),
    }
    return result
