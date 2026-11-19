"""多轮模块的公开协议与证据校验；不负责提问选择或风险计算。"""
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol

from .config import require
from .contracts import check_schema, validate_shape
from .dialogue_config import FRAMES, digest, exact_keys


class ScenarioGenerator(Protocol):
    def generate(self, task: dict) -> dict: ...


class Interviewer(Protocol):
    def ask(self, task: dict, history: list) -> dict: ...


class TurnExtractor(Protocol):
    def extract(self, task: dict, turn: dict, history: list) -> dict: ...


class RiskScoringAgent(Protocol):
    def assess(self, profile: dict) -> dict: ...


class ReportAgent(Protocol):
    def report(self, profile: dict, risk: dict) -> dict: ...


# 兼容0.3接口名称。
RiskEngine = RiskScoringAgent
RiskReporter = ReportAgent


def text_schema(enum=None, empty=False):
    result = {'type':'string','minLength':0 if empty else 1}
    if enum is not None:
        result['enum'] = list(enum)
    return result


def object_schema(fields):
    return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}


def array_schema(element):
    return {'type':'array','items':element}


def observation_schema(unit_ids=None, rule_ids=None):
    slot = object_schema({'slot_id':text_schema(),'value':text_schema(),'quote':text_schema()})
    # intensity 为可选 1–5 Likert 强度；缺省时由 conflict_resolver 按参照框架补默认值。
    # 内部校验器不支持 minimum/maximum，故用 enum。
    evidence = {
        'type': 'object',
        'properties': {
            'rule_id': text_schema(rule_ids),
            'quote': text_schema(),
            'rationale': text_schema(),
            'intensity': {'type': 'integer', 'enum': [1, 2, 3, 4, 5]},
        },
        'required': ['rule_id', 'quote', 'rationale'],
        'additionalProperties': False,
    }
    observation = object_schema({
        'unit_id':text_schema(unit_ids),'status':text_schema(['covered','partial','ambiguous','declined','not_applicable']),
        'quote':text_schema(),'reference_frame':text_schema(FRAMES),'subject':text_schema(['self','other','unclear']),
        'context_turn_ids':array_schema(text_schema()),'slots':array_schema(slot),
        'evidence':array_schema(evidence),'reason':text_schema()})
    background = object_schema({'item_id':text_schema(['F01','F02','F03','F04']),
                                'quote':text_schema(),'description':text_schema(),
                                'reference_frame':text_schema(FRAMES),'subject':text_schema(['self','other','unclear'])})
    schema = object_schema({'turn_id':text_schema(),'observations':array_schema(observation),
                            'background':array_schema(background)})
    # 经历为可选独立通道；不要求模型为没有经历的回答补造记录。
    detail = object_schema({'field':text_schema(['role','form','frequency','recency','current_status','adult_trust']),
                            'value':text_schema(), 'quote':text_schema()})
    event = object_schema({'quote':text_schema(), 'subject':text_schema(['self','other','unclear']),
                           'reference_frame':text_schema(['real_event_self_report']),
                           'details':array_schema(detail)})
    schema['properties']['experiences'] = array_schema(event)
    check_schema(schema)
    return schema


@dataclass(frozen=True)
class ValidatedTurn:
    turn_id: str
    observations: tuple
    evidence: tuple
    background: tuple
    experiences: tuple = ()


def quote_span(answer, quote):
    require(isinstance(quote,str) and quote.strip() and answer.count(quote) == 1,
            'quote必须在本轮学生回答中唯一、逐字出现；重复子串请扩大引用范围')
    start = answer.index(quote)
    return {'start':start,'end':start+len(quote),'unit':'unicode_codepoint','end_exclusive':True}


def validate_question(value):
    exact_keys(value, ['question'], 'A2输出')
    question = value['question']
    require(isinstance(question,str) and question.strip() and len(question) <= 1200, 'A2须返回一个非空且不超过1200字的问题')
    return question.strip()


def validate_turn(task, turn, history, result, cfg):
    views = {u['unit_id']:u for u in task['allowed_units']}
    allowed_rules = {r for u in views.values() for r in u['rule_ids']}
    validate_shape(result, observation_schema(list(views), sorted(allowed_rules)))
    require(result['turn_id'] == turn['turn_id'] == task['turn_id'], 'A3输出的turn_id与当前任务不一致')
    require(turn['task_id'] == task['task_id'], '回答不属于当前提问任务')
    old = {t['turn_id']:t for t in history if t['scenario_instance_id'] == task['scenario_instance_id']}
    observations, evidence, backgrounds, seen = [], [], [], set()
    for candidate in result['observations']:
        uid = candidate['unit_id']
        unit = views[uid]
        if candidate['status'] in ('declined','not_applicable'):
            require(task['target_unit_id'] == uid,
                    'declined/not_applicable只能用于本轮直接追问的目标单元；开场或顺带未提及的单元必须省略')
        key = (uid, candidate['reference_frame'], candidate['subject'])
        require(key not in seen, '同轮同单元、参照方式和主体只能有一条观察；多个方向放在其evidence中')
        seen.add(key)
        span = quote_span(turn['answer'], candidate['quote'])
        refs = candidate['context_turn_ids']
        require(len(refs) == len(set(refs)) and set(refs).issubset(old), '上下文只能引用同情境实例中已完成的轮次')
        if candidate['reference_frame'] == 'real_event_self_report':
            # 假设情境的回答中自发出现真实经历时，建立单独的自述事件关联。
            prior_events = [o['event_id'] for tid in refs for o in old[tid].get('validated_observations', [])
                            if o['reference_frame'] == 'real_event_self_report' and o['subject'] == candidate['subject']]
            event_id = prior_events[0] if len(set(prior_events)) == 1 else 'SELF_' + digest([task['session_id'],turn['turn_id'],candidate['subject']])[:16]
        elif candidate['reference_frame'] == 'habitual_self_report':
            event_id = 'HABIT_' + digest([task['session_id'],task['scenario_instance_id']])[:16]
        else:
            event_id = task['event_id']
        slots = candidate['slots']
        ids = [s['slot_id'] for s in slots]
        permitted_slots = {s['slot_id'] for s in unit['required_slots']}
        require(len(ids) == len(set(ids)) and set(ids).issubset(permitted_slots), f'{uid}槽位越界或重复')
        for slot in slots:
            quote_span(turn['answer'], slot['quote'])
        if candidate['status'] == 'covered':
            require(set(ids) == permitted_slots, f'{uid}标记covered必须完整提供该单元槽位')
        if candidate['status'] in ('declined','not_applicable'):
            require(not slots and not candidate['evidence'], '拒答/不适用不能同时生成槽位值或方向证据')
        oid = 'OB_' + digest([task['session_id'],turn['turn_id'],uid,candidate['reference_frame'],candidate['subject']])[:20]
        common = dict(session_id=task['session_id'], scenario_id=task['scenario_id'],
                      scenario_instance_id=task['scenario_instance_id'],condition_id=task['condition_id'],
                      event_id=event_id,turn_id=turn['turn_id'],question_id=task['question_id'],
                      unit_id=uid,reference_frame=candidate['reference_frame'],subject=candidate['subject'],
                      reference_period=unit['reference_period'],context_turn_ids=refs)
        records = []
        duplicates = set()
        for item in candidate['evidence']:
            require(item['rule_id'] in unit['rule_ids'], f'{uid}证据使用了本单元/本轮未允许的规则')
            rule = cfg.rules[item['rule_id']]
            quote_location = quote_span(turn['answer'], item['quote'])
            ekey = (item['rule_id'],item['quote'])
            if ekey in duplicates:
                continue
            duplicates.add(ekey)
            eid = 'DEV_' + digest([oid,*ekey])[:20]
            intensity = item.get('intensity')
            if intensity is not None:
                require(type(intensity) is int and 1 <= intensity <= 5, 'evidence.intensity须为1—5整数')
            record = {**common,**item,'evidence_id':eid,'observation_id':oid,
                      'source_item_ids':[i for i in rule['item_ids'] if i in unit['source_item_ids']],
                      'variable_id':rule['variable_id'],'direction':rule['direction'],
                      'source_span':quote_location,'context_only':False,
                      'validation_level':'structure_source_scope_only'}
            if 'intensity' not in record:
                record['intensity'] = None
            records.append(record)
            evidence.append(record)
        eligible = candidate['subject'] == 'self' and candidate['reference_frame'] == unit['reference_frame']
        observation = {**common,'observation_id':oid,'status':candidate['status'],
                       'quote':candidate['quote'],'source_span':span,'slots':deepcopy(slots),
                       'reason':candidate['reason'],'coverage_eligible':eligible,
                       'source_item_ids':unit['source_item_ids'],'target_variable_ids':unit['target_variable_ids'],
                       'evidence_ids':[r['evidence_id'] for r in records]}
        observations.append(observation)
    for candidate in result['background']:
        location = quote_span(turn['answer'], candidate['quote'])
        backgrounds.append({**deepcopy(candidate),'context_id':'CTX_'+digest([task['session_id'],turn['turn_id'],candidate])[:20],
                            'turn_id':turn['turn_id'],'scenario_id':task['scenario_id'],
                            'scenario_instance_id':task['scenario_instance_id'],'source_span':location,
                            'context_only':True,'included_in_core_or_risk':False})
    experiences=[]
    for index,event in enumerate(result.get('experiences',[])):
        span=quote_span(turn['answer'],event['quote'])
        for detail in event['details']:
            quote_span(turn['answer'],detail['quote'])
            require(detail['quote'] in event['quote'], '经历字段的原话必须来自当前事件')
            allowed = {'role':['perpetrator','victim','observer','unknown'],
                       'form':['physical','verbal','relational','online','unknown'],
                       'current_status':['ongoing','ended','unknown'],
                       'adult_trust':['trust','doubt','unknown']}.get(detail['field'])
            require(allowed is None or detail['value'] in allowed, '经历字段取值越界')
        experiences.append({**deepcopy(event),'experience_id':'EXP_'+digest([task['session_id'],turn['turn_id'],index])[:20],
                            'turn_id':turn['turn_id'],'scenario_instance_id':task['scenario_instance_id'],
                            'source_span':span,'included_in_risk_score':False,
                            'validation_level':'structure_source_scope_only'})
    return ValidatedTurn(turn['turn_id'],tuple(observations),tuple(evidence),tuple(backgrounds),tuple(experiences))
