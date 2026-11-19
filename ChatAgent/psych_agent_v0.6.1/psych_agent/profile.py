"""确定性的心理画像汇总。0.4增加明确标记的流程测试值与固定测试置信度。"""
from copy import deepcopy
from .facets import summarize
from .experience import build_experience
from .evidence_labels import ensure_profile_refs

from .config import require
from .dialogue_config import digest
from .measurement_controller import coverage_report


def direction_value(directions, scoring):
    directions=set(directions)-{'unclear'}
    if not directions:
        return scoring['direction_values']['unclear']
    if directions=={'higher'}:
        return scoring['direction_values']['higher']
    if directions=={'lower'}:
        return scoring['direction_values']['lower']
    return None  # 同方面冲突不自动变成中等能力。


def build_profile(state, cfg):
    fallback_turns = {t['turn_id'] for t in state['turns']
                      if (t.get('response_quality') or {}).get('a3_fallback_used')}
    ledger = [deepcopy(e) for t in state['turns'] for e in t['validated_evidence']]
    observations = [deepcopy(o) for t in state['turns'] for o in t['validated_observations']
                    if o.get('turn_id') not in fallback_turns]
    core = [e for e in ledger if e['subject'] in cfg.evidence_quality['eligible_subjects']
            and e['reference_frame'] in cfg.evidence_quality['eligible_reference_frames']
            and not e['context_only']
            and e.get('turn_id') not in fallback_turns]
    core_ids = {e['evidence_id'] for e in core}
    excluded = []
    for e in ledger:
        if e['evidence_id'] in core_ids:
            continue
        row = deepcopy(e)
        if e.get('turn_id') in fallback_turns:
            row['exclusion_reason'] = 'a3_extraction_fallback'
        elif e.get('context_only'):
            row['exclusion_reason'] = 'context_only'
        elif e.get('subject') not in cfg.evidence_quality['eligible_subjects']:
            row['exclusion_reason'] = 'ineligible_subject'
        elif e.get('reference_frame') not in cfg.evidence_quality['eligible_reference_frames']:
            row['exclusion_reason'] = 'ineligible_reference_frame'
        else:
            row['exclusion_reason'] = 'other'
        excluded.append(row)
    evidence_by_id = {e['evidence_id']: e for e in core}
    coverage = coverage_report(state,cfg)
    variables = []
    conflict_facets = []
    for vid, definition in cfg.base.variables.items():
        groups={}
        for obs in observations:
            if vid not in obs['target_variable_ids'] or obs['subject']!='self' or obs['reference_frame']=='unclear':
                continue
            if obs['status'] in ('declined','not_applicable'):
                continue
            key=(obs['unit_id'],obs['event_id'],obs['condition_id'],obs['reference_frame'],obs['reference_period'])
            group=groups.setdefault(key,{'group_id':'GR_'+digest([state['session_id'],vid,*key])[:20],
                  'variable_id':vid,'unit_id':obs['unit_id'],'facet':cfg.units[obs['unit_id']]['facet'],
                  'event_id':obs['event_id'],'condition_id':obs['condition_id'],'reference_frame':obs['reference_frame'],
                  'reference_period':obs['reference_period'],'scenario_ids':set(),'scenario_instance_ids':set(),
                  'source_item_ids':set(),'observation_ids':[],'evidence_ids':[], 'directions':set(),'slot_observations':[]})
            group['scenario_ids'].add(obs['scenario_id'])
            group['scenario_instance_ids'].add(obs['scenario_instance_id'])
            group['source_item_ids'].update(obs['source_item_ids'])
            group['observation_ids'].append(obs['observation_id'])
            group['slot_observations'].extend({'turn_id':obs['turn_id'],**s} for s in obs['slots'])
            relevant=[e for e in core if e['observation_id']==obs['observation_id'] and e['variable_id']==vid]
            group['evidence_ids'].extend(e['evidence_id'] for e in relevant)
            group['directions'].update(e['direction'] for e in relevant)
        serial=[]
        for group in groups.values():
            group={k:sorted(v) if isinstance(v,set) else v for k,v in group.items()}
            group['evidence_ids']=sorted(set(group['evidence_ids']))
            group['observation_ids']=sorted(set(group['observation_ids']))
            group['test_value']=direction_value(group['directions'],cfg.variable_scoring)
            serial.append(group)
        relevant=[e for e in core if e['variable_id']==vid]
        directions={e['direction'] for e in relevant if e['direction']!='unclear'}
        status = ('not_observed' if not serial else 'descriptive_observations_only' if not directions else
                  'multiple_directions_by_facet_or_context' if len(directions)>1 else 'directional_observations')
        facets, value, confidence = summarize(serial, vid, cfg, evidence_by_id=evidence_by_id)
        for facet in facets:
            if facet.get('status') == 'resolved_conflict' and facet.get('conflict_audit'):
                conflict_facets.append({'variable_id': vid, 'facet_id': facet['facet_id'],
                                        **deepcopy(facet['conflict_audit'])})
        variables.append({'variable_id':vid,'name':definition['name'],'status':status,'value':value,
                          'confidence': confidence,
                          'confidence_mode':'engineering_facet_coverage_intensity',
                          'feature_weight':cfg.variable_scoring['variable_weights'][vid],
                          'scoring_status':cfg.variable_scoring['scoring_status'],
                          'source_risk_role':definition['source_risk_role'],'interpretation_boundary':definition['interpretation_boundary'],
                          'facets':facets, 'groups':serial,'coverage_units':[r for r in coverage['units'] if vid in r['target_variable_ids']]})
    result={'schema_version':'0.6.1','profile_id':'PROFILE_'+state['session_id'],
            'purpose':'scenario_dialogue_psychological_profile','config_set_id':cfg.config_set_id,
            'config_manifest_path':'config/config_manifest.json','source_state_file':'dialogue_state.json',
            'session_id':state['session_id'],'plan_id':state['plan_id'],'synthetic':state['synthetic'],
            'session_status':state['status'],'stop_reason':state['stop_reason'],
            'coverage':coverage,'variables':variables,'evidence_ledger':core,'excluded_evidence':excluded,
            'conflict_resolutions': conflict_facets,
            'experience':build_experience(state),
            'context':[deepcopy(c) for t in state['turns'] for c in t['background']],
            'scenario_instances':[deepcopy(e['instance']) for e in state['entries'] if e['instance']],
            'test_scoring_notice':cfg.confidence_policy['display_warning'],
            'note':'按内容、情境及来源描述本次表达。value由方向×强度×框架权重得出；冲突须写明原因，消解值满分权重计入风险分并写入conflict_resolutions；不确定性进工程置信。同一事件重复表述不提高权重。报告展示使用evidence_ref。'}
    ensure_profile_refs(result)
    return result


def validate_profile(profile, cfg):
    require(isinstance(profile,dict) and profile.get('schema_version')=='0.6.1', '画像格式版本无效')
    require(profile.get('config_set_id')==cfg.config_set_id
            and profile.get('config_manifest_path')=='config/config_manifest.json', '画像使用其他配置集合')
    require(profile.get('profile_id')=='PROFILE_'+profile.get('session_id',''), '画像编号与访谈编号不一致')
    require(profile.get('purpose')=='scenario_dialogue_psychological_profile', '画像用途不符')
    require([v['variable_id'] for v in profile['variables']]==list(cfg.base.variables), '画像变量与原量表不一致')
    evidence=profile['evidence_ledger']
    ids=[e['evidence_id'] for e in evidence]
    require(len(ids)==len(set(ids)), '画像含重复证据ID')
    for e in evidence:
        require(e['rule_id'] in cfg.rules, '画像含未知证据规则')
        rule=cfg.rules[e['rule_id']]
        require(e['variable_id']==rule['variable_id'] and e['unit_id']==rule['unit_id'] and e['direction']==rule['direction'], '画像证据与规则不一致')
        require(e['subject']=='self' and e['reference_frame']!='unclear' and e['context_only'] is False, '背景或第三方证据混入核心画像')
        require(set(e['source_item_ids']).issubset(rule['item_ids']), '画像证据的原题来源不符')
    for variable in profile['variables']:
        values=[]
        for group in variable['groups']:
            expected=direction_value(group['directions'],cfg.variable_scoring)
            require(group.get('test_value')==expected, '画像测量组测试值与方向不一致')
            if expected is not None:
                values.append(expected)
        evidence_by_id = {e['evidence_id']: e for e in profile['evidence_ledger']}
        facets, expected, confidence = summarize(variable['groups'], variable['variable_id'], cfg, evidence_by_id=evidence_by_id)
        require(variable.get('facets') == facets and variable.get('value') == expected, 'Facet或变量值与证据组不一致')
        require(variable.get('confidence') == confidence and variable.get('confidence_mode')=='engineering_facet_coverage_intensity', '变量覆盖置信度不一致')
    return profile
