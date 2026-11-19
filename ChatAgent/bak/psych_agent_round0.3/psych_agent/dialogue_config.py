"""多轮测量配置。原量表映射→情境绑定→计划范围→单元适用条件逐层取交集。"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .config import id_list, index_rows, load_config, require
from .io_utils import read_json

FRAMES = ('hypothetical_intent', 'habitual_self_report', 'real_event_self_report',
          'general_belief', 'task_performance', 'unclear')
STATUSES = ('not_asked', 'partial', 'covered', 'ambiguous', 'declined', 'not_applicable')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def exact_keys(value, keys, label):
    require(isinstance(value, dict) and set(value) == set(keys), f'{label}字段不符合接口约定')


@dataclass(frozen=True)
class DialogueConfig:
    base: object
    units: dict
    rules: dict
    scenarios: dict
    policy: dict
    plans: dict
    risk_rules: dict
    fingerprints: dict

    @property
    def root(self):
        return self.base.root

    def condition(self, entry):
        return deepcopy(next(c for c in self.scenarios[entry['scenario_id']]['conditions']
                             if c['condition_id'] == entry['condition_id']))

    def unit_views(self, entry):
        bindings = self.base.scenario_bindings(entry['scenario_id'])
        result = {}
        for uid in entry['unit_ids']:
            unit = deepcopy(self.units[uid])
            selected = [i for i in unit['source_item_ids'] if i in entry['active_item_ids']]
            targets = [v for v in unit['target_variable_ids']
                       if any(v in bindings[i]['target_variable_ids'] for i in selected)]
            require(bool(targets), f'{entry["scenario_id"]}/{uid}没有允许的变量方面')
            unit['source_item_ids'] = selected
            unit['target_variable_ids'] = targets
            unit['rule_ids'] = [r for r in unit['rule_ids'] if self.rules[r]['variable_id'] in targets
                               and set(self.rules[r]['item_ids']) & set(selected)]
            result[uid] = unit
        return result

    def applicable(self, unit, facts):
        return all(facts.get(key) in values for key, values in unit['applicability'].items())


def load_dialogue_config(root):
    base = load_config(root)
    root = base.root
    read = lambda name: read_json(root/'config'/name)
    unit_doc = read('measurement_units.json')
    units = index_rows(unit_doc, 'units', 'unit_id')
    rules = index_rows(read('dialogue_rubric.json'), 'rules', 'rule_id')
    scenarios = index_rows(read('dialogue_scenarios.json'), 'scenarios', 'scenario_id')
    policy = read('interview_policy.json')
    plans = index_rows(policy, 'plans', 'plan_id')
    risk = read('risk_profile_rules.json')
    require(set(unit_doc['background_item_ids']) == {i for i in base.items if base.items[i]['context_only']}, '背景范围必须与原量表F类一致')
    covered_items = set()
    for uid, unit in units.items():
        sources = id_list(unit.get('source_item_ids'), uid+'.source_item_ids')
        targets = id_list(unit.get('target_variable_ids'), uid+'.target_variable_ids')
        require(bool(sources) and set(sources).issubset(base.items), f'{uid}原题来源无效')
        require(all(not base.items[i]['context_only'] for i in sources), f'{uid}不能主动测量F类背景')
        require(bool(targets) and set(targets).issubset(base.variables), f'{uid}变量无效')
        require(all(all(v in base.items[i]['variable_ids'] for v in targets) for i in sources), f'{uid}违反原题映射')
        require(unit.get('reference_frame') in FRAMES[:-1], f'{uid}回答参照无效')
        require(isinstance(unit.get('required_slots'), list) and unit['required_slots'], f'{uid}缺少槽位')
        slot_ids = [s['slot_id'] for s in unit['required_slots']]
        id_list(slot_ids, uid+'.slots')
        require(all(isinstance(s.get('description'), str) and s['description'] for s in unit['required_slots']), f'{uid}槽位说明无效')
        require(isinstance(unit.get('question_template'), str) and unit['question_template'].strip(), f'{uid}问题模板缺失')
        require(isinstance(unit.get('applicability'), dict), f'{uid}适用条件无效')
        require(set(id_list(unit.get('rule_ids'), uid+'.rule_ids')).issubset(rules), f'{uid}规则引用无效')
        require(bool(unit['rule_ids']), f'{uid}没有证据规则')
        covered_items.update(sources)
    require(covered_items == {i for i in base.items if not base.items[i]['context_only']}, '所有核心原题必须有测量单元来源关联')
    for rid, rule in rules.items():
        require(rule.get('unit_id') in units, f'{rid}缺少有效unit_id')
        unit = units[rule['unit_id']]
        require(rid in unit['rule_ids'], f'{rid}没有被所属单元引用')
        require(rule.get('variable_id') in unit['target_variable_ids'], f'{rid}变量超出单元')
        sources = id_list(rule.get('item_ids'), rid+'.item_ids')
        require(bool(sources) and set(sources).issubset(unit['source_item_ids']), f'{rid}来源超出单元')
        require(all(rule['variable_id'] in base.items[i]['variable_ids'] for i in sources), f'{rid}违反原题映射')
        require(rule.get('context_only') is False and rule.get('direction') in ('higher','lower','unclear'), f'{rid}方向或背景标记无效')
        require(all(isinstance(rule.get(k), str) and rule[k] for k in ('criterion','do_not_infer_when')), f'{rid}缺少语义准则')
    require(set(scenarios) == set(base.scenarios), '多轮情境必须对应现有六类蓝图')
    for sid, scenario in scenarios.items():
        conditions = scenario.get('conditions')
        require(isinstance(conditions, list) and conditions, f'{sid}缺少情境条件')
        ids = id_list([c['condition_id'] for c in conditions], sid+'.conditions')
        require('base' in ids, f'{sid}缺少基础条件')
        for c in conditions:
            require(c['parent_condition_id'] is None or c['parent_condition_id'] in ids, f'{sid}条件父节点不存在')
            require(c['parent_condition_id'] != c['condition_id'], f'{sid}条件不能指向自己')
            require(isinstance(c['facts'], dict) and c['facts'], f'{sid}缺少固定事实')
            require(all(isinstance(k,str) and isinstance(v,str) for k,v in c['facts'].items()), f'{sid}事实必须为字符串字段')
            require(isinstance(c['text'],str) and c['text'].strip(), f'{sid}情境文本缺失')
    require(type(policy.get('max_attempts_per_unit')) is int and 1 <= policy['max_attempts_per_unit'] <= 5, '单元追问上限无效')
    require(policy.get('default_plan_id') in plans, '默认访谈计划不存在')
    require(policy.get('background_policy') == 'spontaneous_only_excluded_from_core_and_risk', 'F类背景边界不符')
    for key in ('stop_commands', 'skip_commands'):
        require(bool(id_list(policy.get(key), key)), f'{key}不能为空')
    require(not set(policy['stop_commands']) & set(policy['skip_commands']), '结束与跳过命令不能重叠')
    cfg = DialogueConfig(base, units, rules, scenarios, policy, plans, risk, {})
    for pid, plan in plans.items():
        require(isinstance(plan.get('entries'),list) and plan['entries'], f'{pid}情境计划为空')
        require(type(plan.get('max_total_turns')) is int and 1 <= plan['max_total_turns'] <= 200, f'{pid}总预算无效')
        for entry in plan['entries']:
            exact_keys(entry, ['scenario_id','condition_id','active_item_ids','unit_ids','max_turns'], pid+'.entry')
            sid = entry['scenario_id']
            require(sid in scenarios, f'{pid}未知情境')
            require(entry['condition_id'] in [c['condition_id'] for c in scenarios[sid]['conditions']], f'{pid}未知情境条件')
            require(type(entry['max_turns']) is int and 1 <= entry['max_turns'] <= 40, f'{pid}情境预算无效')
            selected = id_list(entry['active_item_ids'], pid+'.active_item_ids')
            require(bool(selected) and set(selected).issubset(base.scenario_bindings(sid)), f'{pid}题目超出蓝图绑定')
            require(bool(id_list(entry['unit_ids'], pid+'.unit_ids')) and set(entry['unit_ids']).issubset(units), f'{pid}单元范围无效')
            cfg.unit_views(entry)
    exact_keys(risk['role_variables'], ['bully','victim','bully_victim'], '角色输出')
    require(risk.get('mode') == 'source_association_only', '默认风险引擎只组织原表相关因素')
    for vids in [*risk['role_variables'].values(), risk['shared_variables']]:
        require(set(id_list(vids, 'risk.variables')).issubset(base.variables), '风险配置引用未知变量')
    names = ['psychological_variable.json','questionnaire_mapping.json','scenario_blueprint.json',
             'measurement_units.json','dialogue_rubric.json','dialogue_scenarios.json','interview_policy.json','risk_profile_rules.json']
    paths = [root/'config'/name for name in names]
    paths += sorted((root/'prompts').glob('*.md')) + sorted((root/'schemas').glob('*.json'))
    cfg.fingerprints.update({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    return cfg
