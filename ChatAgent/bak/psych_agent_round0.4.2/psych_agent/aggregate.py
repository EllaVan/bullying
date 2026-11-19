"""纯Python证据汇总：不调用LLM，不生成分数、概率或角色结论。"""
from .evidence import ValidatedEvidence


def aggregate(batch: ValidatedEvidence, cfg):
    if not isinstance(batch, ValidatedEvidence):
        raise TypeError('请先通过validate_extraction校验输入')
    context = [e for e in batch.evidence if e['context_only']]
    other = [e for e in batch.evidence if not e['context_only'] and
             (e['subject'] != 'self' or e['source_kind'] in ['third_party_report','unclear'])]
    core = [e for e in batch.evidence if not e['context_only'] and e['subject'] == 'self'
            and e['source_kind'] not in ['third_party_report','unclear']]
    variables = []
    for vid in cfg.scope['active_variable_ids']:
        records = [e for e in core if e['variable_id'] == vid]
        groups = {}
        for evidence in records:
            # 同一事件、同一变量、同一回答类型的多次表述汇成一个观察组。
            # 多条引用保留，不能因多说几次就增加某个特质的强度。
            key = (evidence['event_id'], vid, evidence['source_kind'])
            bucket = groups.setdefault(key, {'event_id':key[0], 'source_kind':key[2],
                                             'directions':set(), 'evidence_ids':[]})
            bucket['directions'].add(evidence['direction'])
            bucket['evidence_ids'].append(evidence['evidence_id'])
        observations = [{**group,'directions':sorted(group['directions']),
                         'evidence_ids':sorted(set(group['evidence_ids']))} for _,group in sorted(groups.items())]
        directions = {e['direction'] for e in records if e['direction'] != 'unclear'}
        if not records:
            status = 'insufficient_evidence'
        elif not directions:
            status = 'ambiguous_evidence'
        elif len(directions) > 1:
            status = 'multiple_directions_observed'
        else:
            status = 'directional_evidence_observed'
        variables.append({'variable_id':vid,'name':cfg.variables[vid]['name'],
                          'status':status,'value':None,'confidence':None,
                          'observation_group_count':len(observations),
                          'source_kinds':sorted({e['source_kind'] for e in records}),
                          'observations':observations,
                          'note':'方向描述仅针对本次表达；不能视为稳定特质、已验证能力或风险程度。'})
    return {'case_id':batch.case_id,'scenario_id':batch.scenario_id,
            'purpose':'engineering_evidence_summary','semantic_review_status':'not_reviewed',
            'variables':variables,'context_evidence':context,'excluded_subject_or_source_evidence':other,
            'evidence_ledger':list(batch.evidence),'extractor_gap_notes':list(batch.gaps),
            'duplicate_candidates_removed':batch.duplicate_candidates_removed,'risk_result':None,
            'limitations':['所有变量数值与置信度保持null。','观察组数量不是信度或独立测量次数。',
                           '代码只验证可检查的格式和来源；语义判定规则及抽取结果仍需独立人工评阅。',
                           '来自不同条件的不同方向不自动视为矛盾，更不判断撒谎。']}
