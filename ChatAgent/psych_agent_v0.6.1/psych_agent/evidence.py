"""校验可检查的事实：格式、原文位置、映射、主体和来源。

本模块不能自动证明证据语义成立；语义是否满足criterion仍须独立评阅。
"""
from dataclasses import dataclass
import hashlib
import json
import re

from .config import require
from .contracts import validate_shape


@dataclass(frozen=True)
class ValidatedEvidence:
    case_id: str
    scenario_id: str
    evidence: tuple
    gaps: tuple
    duplicate_candidates_removed: int


def validate_case(case, cfg):
    validate_shape(case, cfg.case_schema)
    require(bool(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', case['case_id'])), 'case_id只能包含字母、数字、下划线和短横线，长度1—64')
    require(case['scenario_id'] == cfg.scope['scenario_id'], '案例不属于本轮情境')
    turns = [turn['turn_id'] for turn in case['turns']]
    require(len(turns) == len(set(turns)), '案例存在重复turn_id')
    return case


def validate_extraction(case, result, cfg):
    validate_case(case, cfg)
    validate_shape(result, cfg.extraction_schema)
    require(result['case_id'] == case['case_id'], '抽取结果case_id与输入不一致')
    active_variables = cfg.scope['active_variable_ids']
    invalid_gaps = [f"gaps[{index}].variable_id={gap['variable_id']!r}"
                    for index, gap in enumerate(result['gaps'])
                    if gap['variable_id'] not in active_variables]
    require(not invalid_gaps, 'gaps使用了本轮未允许的变量：' + '；'.join(invalid_gaps)
            + '；本轮允许：' + ', '.join(active_variables))
    turns = {turn['turn_id']:turn for turn in case['turns']}
    allowed_rules = cfg.allowed_rules()
    checked = []
    seen = set()
    duplicates = 0
    for candidate in result['evidence']:
        require(candidate['rule_id'] in allowed_rules, '证据使用了本轮未允许的rule_id')
        require(candidate['turn_id'] in turns, '证据引用不存在的turn_id')
        rule = allowed_rules[candidate['rule_id']]
        turn = turns[candidate['turn_id']]
        quote = candidate['quote']
        require(turn['answer'].count(quote) == 1, 'quote必须在学生answer中唯一、逐字出现；重复子串请扩大引用范围')
        kind = candidate['source_kind']
        subject = candidate['subject']
        require((kind == 'third_party_report') == (subject == 'other'), '第三方转述必须明确标记other主体，反之亦然')
        permitted = {
            'hypothetical': {'hypothetical_intent','general_belief','third_party_report','unclear'},
            'real_event': {'self_report','general_belief','third_party_report','unclear'},
            'mixed': {'hypothetical_intent','self_report','general_belief','third_party_report','unclear'},
            'general_opinion': {'general_belief','third_party_report','unclear'},
        }
        require(kind in permitted[turn['response_context']], 'source_kind与实验记录的response_context不兼容')
        start = turn['answer'].index(quote)
        key = (candidate['rule_id'], candidate['turn_id'], start, start+len(quote), kind, subject)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        digest = hashlib.sha256(json.dumps([case['case_id'],*key], ensure_ascii=False).encode()).hexdigest()[:16]
        checked.append({**candidate, 'evidence_id':'EV_'+digest, 'case_id':case['case_id'],
                        'scenario_id':case['scenario_id'], 'event_id':turn['event_id'],
                        'question_id':turn['question_id'], 'item_ids':list(rule['item_ids']),
                        'variable_id':rule['variable_id'], 'direction':rule['direction'],
                        'context_only':rule['context_only'],
                        'source_span':{'start':start,'end':start+len(quote),'unit':'unicode_codepoint','end_exclusive':True},
                        'validation_level':'structure_quote_and_mapping_only',
                        'semantic_review_status':'not_reviewed'})
    gap_variables = []
    for gap in result['gaps']:
        gap_variables.append(gap['variable_id'])
    require(len(gap_variables) == len(set(gap_variables)), 'gaps包含重复变量')
    return ValidatedEvidence(case['case_id'],case['scenario_id'],tuple(checked),tuple(result['gaps']),duplicates)
