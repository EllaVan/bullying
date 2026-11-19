"""A4：四类独立工程风险分数（0—100），含旁观；无联合概率、归一化或概率转换。"""
from copy import deepcopy
import math
from .config import require
from .dialogue_config import exact_keys

ROLES = ('bully', 'victim', 'bully_victim', 'bystander')
FORMS = ('physical', 'verbal', 'relational')
SEMANTICS = 'independent_risk_scores_0_100'
EXPERIENCE_BOOST_MAP = {
    'perpetrator': ('bully', 'perpetrator_to_bully'),
    'victim': ('victim', 'victim_to_victim'),
    'observer': ('bystander', 'observer_to_bystander'),
}


def number(value, maximum, nullable=True):
    return (value is None and nullable) or (type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum)


def model_input(profile):
    return {'schema_version': '0.6.1', 'model_input_id': 'MODEL_INPUT_' + profile['session_id'],
            'profile_id': profile['profile_id'], 'source_profile_file': 'profile.json',
            'config_set_id': profile['config_set_id'], 'session_id': profile['session_id'],
            'synthetic': profile['synthetic'],
            'features': [{k: deepcopy(v[k]) for k in ('variable_id', 'value', 'confidence', 'confidence_mode',
                         'feature_weight', 'scoring_status', 'groups', 'facets')} for v in profile['variables']],
            'evidence': deepcopy(profile['evidence_ledger']), 'coverage': deepcopy(profile['coverage']),
            'conflict_resolutions': deepcopy(profile.get('conflict_resolutions', [])),
            'scenario_conditions': [{'scenario_id': s['scenario_id'], 'condition_id': s['condition_id'], 'facts': s['facts']}
                                   for s in profile['scenario_instances']],
            'experience_file': 'experience.json', 'note': '经历单列；假设、第三方、未观察不转化为已发生事件。冲突消解审计随画像传入。'}


def _risk_support(value, effect):
    require(effect in ('risk_increasing', 'protective'), '风险方向配置无效')
    require(number(value, 1), '变量值须为0—1有限数值或null')
    return None if value is None else (value if effect == 'risk_increasing' else 1 - value)


def _weighted_mean(items, digits=None):
    items = [(v, w) for v, w in items if v is not None]
    total = sum(w for _, w in items)
    value = sum(v * w for v, w in items) / total if total else None
    return round(value, digits) if value is not None and digits is not None else value


def level_for(score, thresholds):
    """半开区间：[0,关注)、[关注,高)、[高,100]，端点没有歧义。"""
    if score is None:
        return 'insufficient'
    return 'low' if score < thresholds[0] else 'attention' if score < thresholds[1] else 'high'


def _form_value(variable, form, profile, cfg):
    from .facets import summarize
    forms = {s['scenario_id']: s['facts']['form'] for s in profile['scenario_instances']}
    groups = [g for g in variable['groups'] if any(forms.get(s) == form for s in g['scenario_ids'])]
    evidence_by_id = {e['evidence_id']: e for e in profile.get('evidence_ledger', [])}
    return summarize(groups, variable['variable_id'], cfg, evidence_by_id=evidence_by_id)[1]


def _experience_role_boosts(profile, cfg):
    boost_cfg = cfg.get('experience_role_boost') or {}
    if not boost_cfg.get('enabled'):
        return {}
    experience = profile.get('experience') or {}
    roles_seen = {e.get('role') for e in experience.get('events', []) if e.get('role') and e['role'] != 'unknown'}
    boosts = {}
    for experience_role, (risk_role, key) in EXPERIENCE_BOOST_MAP.items():
        if experience_role in roles_seen:
            boosts[risk_role] = float(boost_cfg.get(key, 0.0))
    return boosts


def _role_conflict_share(variables, role_variable_ids):
    """该角色变量中已观测 facet 里，冲突面权重占比。"""
    observed_w = 0.0
    conflict_w = 0.0
    for vid in role_variable_ids:
        var = variables.get(vid)
        if not var:
            continue
        for facet in var.get('facets') or []:
            weight = float(facet.get('weight') or 0)
            if weight <= 0 or facet.get('value') is None:
                continue
            observed_w += weight
            if facet.get('status') == 'resolved_conflict' or facet.get('conflict_audit'):
                conflict_w += weight
    if observed_w <= 0:
        return 0.0
    return min(1.0, conflict_w / observed_w)


def confidence_label_for(confidence, policy):
    """将 0—1 工程置信映射为 high/medium/low。"""
    if confidence is None:
        return 'low'
    thresholds = policy.get('conflict_label_thresholds') or {}
    high = float(thresholds.get('high', 0.75))
    medium = float(thresholds.get('medium', 0.5))
    if confidence >= high:
        return 'high'
    if confidence >= medium:
        return 'medium'
    return 'low'


def apply_conflict_confidence(base_confidence, conflict_share, policy):
    """分数轴不变；仅对置信乘 conflict_factor，并生成标签。"""
    penalty = float(policy.get('conflict_penalty', 0.35))
    share = max(0.0, min(1.0, float(conflict_share or 0.0)))
    factor = 1.0 - penalty * share
    if base_confidence is None:
        return None, share, factor, 'low', None
    value = round(max(0.0, min(1.0, float(base_confidence) * factor)), 4)
    label = confidence_label_for(value, policy)
    tag = 'conflict' if share > 0 else None
    return value, share, round(factor, 4), label, tag


class TestRiskScoringAgent:
    """配置权重仅为工程建议；覆盖不够不发布分数。冲突面已在画像层软消解，此处不再整面丢弃。"""
    def __init__(self, cfg):
        self.cfg = cfg

    def assess(self, profile):
        cfg = self.cfg.risk_scoring
        variables = {v['variable_id']: v for v in profile['variables']}
        coverage = profile['coverage']['coverage_fraction'] or 0.0
        quality = profile['coverage']['response_quality']
        denominator = max(1, quality['eligible_response_turns'])
        low_rate = quality['low_information_turns'] / denominator
        fallback_rate = quality['a3_fallback_turns'] / max(1, profile['coverage']['answered_turns'])
        quality_factor = max(0, (1 - self.cfg.confidence_policy['low_information_penalty'] * low_rate)
                             * (1 - self.cfg.confidence_policy['fallback_penalty'] * fallback_rate))
        experience_boosts = _experience_role_boosts(profile, cfg)
        conflict_count = len(profile.get('conflict_resolutions') or [])
        factors, roles = [], []
        for role in ROLES:
            specs = cfg['roles'][role]
            rows = []
            for spec in specs:
                var = variables[spec['variable_id']]
                rows.append({'factor_id': f'RF_{role}_{spec["variable_id"]}', 'role': role, **spec,
                             'variable_value': var['value'], 'risk_support': _risk_support(var['value'], spec['effect']),
                             'confidence': var['confidence'],
                             'evidence_ids': sorted({e for g in var['groups'] for e in g['evidence_ids']}),
                             'source_item_ids': sorted({i for g in var['groups'] for i in g['source_item_ids']})})
            factors.extend(rows)
            observed = [r for r in rows if r['risk_support'] is not None]
            weight_coverage = sum(r['weight'] for r in observed) / sum(r['weight'] for r in rows)
            reasons = []
            if coverage < cfg['minimum_coverage_for_score']:
                reasons.append('plan_coverage_below_minimum')
            if weight_coverage < cfg['minimum_role_weight_coverage']:
                reasons.append('role_weight_coverage_below_minimum')
            if len(observed) < cfg['minimum_observed_features']:
                reasons.append('too_few_observed_variables')
            raw = _weighted_mean([(r['risk_support'], r['weight']) for r in observed])
            score = None if reasons or raw is None else round(100 * raw, cfg['score_round_digits'])
            boost_note = None
            if score is not None and role in experience_boosts and experience_boosts[role] > 0:
                boosted = min(100.0, score + 100.0 * experience_boosts[role])
                boost_note = {'from_score': score, 'boost': experience_boosts[role], 'to_score': round(boosted, cfg['score_round_digits'])}
                score = round(boosted, cfg['score_round_digits'])
            role_var_ids = [s['variable_id'] for s in specs]
            conflict_share = _role_conflict_share(variables, role_var_ids)
            if score is None:
                confidence, conflict_share, conflict_factor, conf_label, conf_tag = apply_conflict_confidence(
                    0.0, conflict_share, self.cfg.confidence_policy)
                confidence = 0.0
                conf_label = 'low'
            else:
                base_confidence = round(weight_coverage * quality_factor *
                    (_weighted_mean([(r['confidence'], r['weight']) for r in observed]) or 0), 4)
                confidence, conflict_share, conflict_factor, conf_label, conf_tag = apply_conflict_confidence(
                    base_confidence, conflict_share, self.cfg.confidence_policy)
            forms = {}
            for form in FORMS:
                form_rows = [(_risk_support(_form_value(variables[s['variable_id']], form, profile, self.cfg), s['effect']), s['weight']) for s in specs]
                available = [(v, w) for v, w in form_rows if v is not None]
                form_cov = sum(w for _, w in available) / sum(w for _, w in form_rows)
                ok = not reasons and len(available) >= cfg['minimum_observed_features'] and form_cov >= cfg['minimum_role_weight_coverage']
                forms[form] = round(100 * _weighted_mean(available), cfg['score_round_digits']) if ok else None
            roles.append({'role': role, 'status': 'insufficient_evidence' if score is None else 'engineering_score',
                          'score': score, 'level': level_for(score, cfg['thresholds'][role]),
                          'thresholds': deepcopy(cfg['thresholds'][role]), 'confidence': confidence,
                          'confidence_mode': 'engineering_coverage_quality_conflict',
                          'confidence_label': conf_label, 'confidence_tag': conf_tag,
                          'conflict_share': round(conflict_share, 4), 'conflict_factor': conflict_factor,
                          'observed_feature_count': len(observed), 'configured_feature_count': len(rows),
                          'weight_coverage': round(weight_coverage, 6), 'unavailable_reasons': reasons,
                          'factor_ids': [r['factor_id'] for r in rows], 'form_scores': forms,
                          'experience_boost': boost_note, 'gate_applied': None})
        result = {'schema_version': '0.6.1', 'risk_result_id': 'RISK_' + profile['session_id'],
                'profile_id': profile['profile_id'], 'model_input_id': 'MODEL_INPUT_' + profile['session_id'],
                'source_profile_file': 'profile.json', 'source_model_input_file': 'risk_model_input.json',
                'config_set_id': profile['config_set_id'], 'session_id': profile['session_id'],
                'synthetic': profile['synthetic'], 'agent_id': 'A4', 'status': 'test_score_only',
                'assessment_target': deepcopy(cfg['assessment_target']), 'role_semantics': SEMANTICS,
                'model_id': cfg['model_id'], 'roles': roles, 'factors': factors, 'score_range': [0, 100],
                'scoring_policy': deepcopy(cfg), 'validation_status': 'uncalibrated_engineering_score',
                'conflict_resolution_count': conflict_count,
                'note': cfg['note'] + ' ' + self.cfg.confidence_policy['display_warning']}
        from .scale_gates import apply_scale_constraints
        return apply_scale_constraints(result, profile, getattr(self.cfg, 'scale_constraints', {}))


def validate_prediction(prediction, profile):
    """外部A4也只接受0—100分数；旧probabilities接口明确拒绝。"""
    exact_keys(prediction, ['schema_version','session_id','profile_id','model_input_id','config_set_id','synthetic',
                           'model_id','assessment_target','role_semantics','scores','confidence','validation_status'], '外部评分结果')
    require(prediction['schema_version'] == '0.6.1' and prediction['role_semantics'] == SEMANTICS, '请使用0.6.1分数接口')
    for key in ('session_id', 'profile_id', 'config_set_id', 'synthetic'):
        require(prediction[key] == profile[key], '外部结果不属于当前画像')
    require(type(prediction['synthetic']) is bool, '模拟标记无效')
    require(prediction['model_input_id'] == 'MODEL_INPUT_' + profile['session_id'], '外部模型输入编号不符')
    require(isinstance(prediction['model_id'],str) and prediction['model_id'].strip(), '缺少模型编号')
    exact_keys(prediction['assessment_target'], ['kind','time_window'], '外部评分目标')
    require(all(isinstance(v,str) and v.strip() for v in prediction['assessment_target'].values()), '评分目标不能为空')
    for key, limit in [('scores',100), ('confidence',1)]:
        exact_keys(prediction[key], ROLES, key)
        require(all(number(v,limit) for v in prediction[key].values()), key + '含越界、布尔或非有限数值')
    require(bool(profile['evidence_ledger']), '无核心证据不能导入评分')
    require(isinstance(prediction['validation_status'],str) and prediction['validation_status'], '缺少验证状态')
    return prediction


class ExternalPredictionRiskScoringAgent:
    def __init__(self, cfg, prediction):
        self.cfg, self.prediction = cfg, deepcopy(prediction)

    def assess(self, profile):
        supplied = validate_prediction(self.prediction, profile)
        result = TestRiskScoringAgent(self.cfg).assess(profile)
        result.update(status='external_model_result', model_id=supplied['model_id'],
                      assessment_target=supplied['assessment_target'], validation_status=supplied['validation_status'])
        policy = self.cfg.confidence_policy
        for row in result['roles']:
            # 外部模型不能绕过本次访谈证据不足门槛。
            if not row['unavailable_reasons']:
                external_conf = supplied['confidence'][row['role']]
                conf, share, factor, label, tag = apply_conflict_confidence(
                    external_conf, row.get('conflict_share') or 0.0, policy)
                row.update(score=supplied['scores'][row['role']], confidence=conf,
                           confidence_mode='external_model_conflict', status='external_score',
                           confidence_label=label, confidence_tag=tag,
                           conflict_share=round(share, 4), conflict_factor=factor)
                row['level'] = level_for(row['score'], row['thresholds'])
            row['form_scores'] = dict.fromkeys(FORMS)
        return result


def validate_risk_result(result, profile):
    require(isinstance(result,dict) and result.get('schema_version') == '0.6.1', '风险结果版本无效')
    for key in ('session_id', 'profile_id', 'config_set_id', 'synthetic'):
        require(result.get(key) == profile[key], '风险结果输入引用不符')
    require(result.get('model_input_id') == 'MODEL_INPUT_' + profile['session_id'], 'A4输入编号不符')
    require(result.get('agent_id') == 'A4' and result.get('role_semantics') == SEMANTICS, '角色分数含义不符')
    require(result.get('score_range') == [0,100], '分数范围不符')
    rows = result.get('roles',[])
    require([r['role'] for r in rows] == list(ROLES), '须输出四个约定角色（含旁观）')
    factors = {f['factor_id']:f for f in result['factors']}
    require(len(factors) == len(result['factors']), '因素编号重复')
    for row in rows:
        require('probability' not in row and 'form_probabilities' not in row, '拒绝旧概率输出')
        require(number(row['score'],100) and number(row['confidence'],1), '分数或置信度无效')
        require(set(row['form_scores']) == set(FORMS) and all(number(v,100) for v in row['form_scores'].values()), '形式分数无效')
        require(row['level'] == level_for(row['score'],row['thresholds']), '等级与阈值不一致')
        require(all(fid in factors and factors[fid]['role'] == row['role'] for fid in row['factor_ids']), '跨角色因素引用')
        if row['unavailable_reasons']:
            require(row['score'] is None and row['level'] == 'insufficient', '证据不足仍输出分数')
    return result

# 名称只为内部旧测试调用保留，不暴露旧概率协议。
EvidenceRiskEngine = TestRiskScoringAgent
ExternalPredictionRiskEngine = ExternalPredictionRiskScoringAgent
