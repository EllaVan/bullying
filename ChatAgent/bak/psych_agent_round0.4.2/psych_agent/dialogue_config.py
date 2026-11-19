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
    risk_scoring: dict
    variable_scoring: dict
    evidence_quality: dict
    confidence_policy: dict
    report_policy: dict
    manifest: dict

    @property
    def root(self):
        return self.base.root

    @property
    def config_set_id(self):
        return self.manifest['config_set_id']

    @property
    def config_references(self):
        return [row['path'] for row in self.manifest['files']]

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
    risk_scoring = read('risk_scoring.json')
    variable_scoring = read('variable_scoring.json')
    evidence_quality = read('evidence_quality.json')
    confidence_policy = read('confidence_policy.json')
    report_policy = read('report_policy.json')
    manifest = read('config_manifest.json')
    require(manifest.get('schema_version') == '1.0' and manifest.get('content_version') == '0.4.2', '配置清单版本无效')
    require(isinstance(manifest.get('config_set_id'),str) and manifest['config_set_id'], '配置清单缺少config_set_id')
    refs = manifest.get('files')
    require(isinstance(refs,list) and refs, '配置清单文件列表为空')
    ref_ids, ref_paths = [], []
    for row in refs:
        exact_keys(row,['config_id','path','required'],'配置清单记录')
        require(isinstance(row['config_id'],str) and row['config_id'], '配置记录缺少编号')
        require(isinstance(row['path'],str) and row['path'].startswith('config/') and '..' not in Path(row['path']).parts, '配置记录必须使用config下的相对路径')
        require(type(row['required']) is bool, '配置记录required必须为布尔值')
        if row['required']:
            require((root/row['path']).is_file(), f'缺少配置文件：{row["path"]}')
        ref_ids.append(row['config_id']); ref_paths.append(row['path'])
    id_list(ref_ids,'config_manifest.config_id')
    id_list(ref_paths,'config_manifest.path')
    for name, document in [('measurement_units',unit_doc),('dialogue_rubric',read('dialogue_rubric.json')),
                           ('dialogue_scenarios',read('dialogue_scenarios.json')),('interview_policy',policy),
                           ('risk_profile_rules',risk),('risk_scoring',risk_scoring),('variable_scoring',variable_scoring),
                           ('evidence_quality',evidence_quality),('confidence_policy',confidence_policy),
                           ('report_policy',report_policy)]:
        require(document.get('version')=='0.4.2', f'{name}版本不是0.4.2')
        require(document.get('config_set_id')==manifest['config_set_id'], f'{name}不属于当前配置集合')
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
    response_quality=policy.get('response_quality')
    exact_keys(response_quality,
               ['brief_response_max_characters','warning_threshold','threshold_operator',
                'alternate_probe_prefix','interpretation_boundary'],'回答质量策略')
    require(type(response_quality['brief_response_max_characters']) is int
            and 1 <= response_quality['brief_response_max_characters'] <= 50,
            '简略回答字符阈值无效')
    require(type(response_quality['warning_threshold']) in (int,float)
            and 0 < response_quality['warning_threshold'] < 1
            and response_quality['threshold_operator']=='greater_than',
            '回答简略度提示阈值无效')
    require(all(isinstance(response_quality[k],str) and response_quality[k].strip()
                for k in ('alternate_probe_prefix','interpretation_boundary')),
            '回答质量策略缺少追问表达或解释边界')
    cfg = DialogueConfig(base, units, rules, scenarios, policy, plans, risk, risk_scoring,
                         variable_scoring, evidence_quality, confidence_policy, report_policy, manifest)
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
    require(risk.get('mode') == 'source_association_with_test_scoring', '风险关联模式与0.4实现不符')
    for vids in [*risk['role_variables'].values(), risk['shared_variables']]:
        require(set(id_list(vids, 'risk.variables')).issubset(base.variables), '风险配置引用未知变量')
    require(variable_scoring.get('mode')=='direction_group_mean_test_only', '变量测试计分模式无效')
    exact_keys(variable_scoring.get('direction_values'),['higher','lower','mixed','unclear'],'变量方向测试值')
    exact_keys(variable_scoring.get('variable_weights'),list(base.variables),'变量等权配置')
    require(all(value==1.0 for value in variable_scoring['variable_weights'].values()), '0.4流程测试要求十变量等权为1.0')
    require(confidence_policy.get('mode')=='fixed_test_value'
            and confidence_policy.get('variable_confidence')==1.0
            and confidence_policy.get('role_confidence')==1.0
            and confidence_policy.get('apply_variable_confidence_to_unobserved') is True
            and confidence_policy.get('human_review_required') is True,
            '0.4流程测试置信度配置无效')
    roles=risk_scoring.get('roles')
    exact_keys(roles,['bully','victim','bully_victim'],'A4角色配置')
    require(risk_scoring.get('agent_id')=='A4' and risk_scoring.get('mode')=='heuristic_equal_weight_test_only', 'A4测试计算配置无效')
    for role, features in roles.items():
        require(isinstance(features,list) and features, f'{role}缺少风险特征')
        ids=[]
        for feature in features:
            exact_keys(feature,['variable_id','effect','weight'],f'{role}风险特征')
            require(feature['variable_id'] in base.variables, f'{role}引用未知变量')
            require(feature['effect'] in ('risk_increasing','protective') and feature['weight']==1.0, f'{role}测试特征方向或权重无效')
            ids.append(feature['variable_id'])
        id_list(ids,role+'.variable_ids')
        expected=set(risk['role_variables'][role]+risk['shared_variables'])
        require(set(ids)==expected, f'{role}的A4测试特征与原变量角色关联不一致')
    require(risk_scoring.get('forms')==['physical','verbal','relational'], 'A4必须输出三种霸凌形式')
    require(report_policy.get('agent_id')=='A5' and report_policy.get('allow_diagnosis') is False
            and 'response_quality' in report_policy.get('sections',[]), 'A5报告边界无效')
    require(evidence_quality.get('background_policy')=='separate_only_excluded_from_core_and_risk', '证据背景边界无效')
    return cfg
