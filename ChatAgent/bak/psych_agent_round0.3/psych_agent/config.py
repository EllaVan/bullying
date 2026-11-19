"""读取和交叉校验只读的测量配置。"""
from dataclasses import dataclass
from pathlib import Path
import re

from .contracts import check_schema
from .io_utils import ValidationError, read_json


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def index_rows(document, collection, key):
    require(isinstance(document, dict), f'{collection}配置顶层必须是对象')
    rows = document.get(collection)
    require(isinstance(rows, list) and bool(rows), f'{collection}必须是非空数组')
    result = {}
    for row in rows:
        require(isinstance(row, dict), f'{collection}记录必须是对象')
        identifier = row.get(key)
        require(isinstance(identifier, str) and identifier, f'{collection}缺少{key}')
        require(identifier not in result, f'{collection}包含重复ID：{identifier}')
        result[identifier] = row
    return result


def id_list(value, label):
    require(isinstance(value, list) and all(isinstance(x, str) for x in value), f'{label}应为字符串数组')
    require(len(value) == len(set(value)), f'{label}有重复ID')
    return value


@dataclass(frozen=True)
class Config:
    root: Path
    variables: dict
    items: dict
    scenarios: dict
    rules: dict
    scope: dict
    aggregation: dict
    case_schema: dict
    extraction_schema: dict

    def scenario_bindings(self, scenario_id=None):
        scenario = self.scenarios[scenario_id or self.scope['scenario_id']]
        if 'item_bindings' in scenario:
            return {b['item_id']: b for b in scenario['item_bindings']}
        # 兼容0.1的旧蓝图。交集只用于旧格式迁移；正式配置应明确所选测量方面。
        return {iid: {'item_id': iid,
                      'target_variable_ids': [v for v in self.items[iid]['variable_ids'] if v in scenario['variable_ids']],
                      'use_condition': '旧格式兼容映射；使用前核对题意与情境适配。'}
                for iid in scenario['item_ids']}

    def allowed_rules(self):
        core = set(self.scope['active_item_ids'])
        context = set(self.scope['optional_context_item_ids'])
        active_variables = set(self.scope['active_variable_ids'])
        bindings = self.scenario_bindings()
        allowed = {}
        for rid, rule in self.rules.items():
            items = set(rule['item_ids'])
            if rule['context_only']:
                if items.issubset(context):
                    allowed[rid] = rule
            elif items.issubset(core) and rule['variable_id'] in active_variables:
                if all(rule['variable_id'] in bindings[iid]['target_variable_ids'] for iid in items):
                    allowed[rid] = rule
        return allowed


def load_config(root, scope_path=None):
    root = Path(root).resolve()
    read = lambda name: read_json(root / 'config' / name)
    variables = index_rows(read('psychological_variable.json'), 'variables', 'variable_id')
    items = index_rows(read('questionnaire_mapping.json'), 'items', 'item_id')
    scenarios = index_rows(read('scenario_blueprint.json'), 'scenarios', 'scenario_id')
    rules = index_rows(read('evidence_rubric.json'), 'rules', 'rule_id')
    selected_scope = Path(scope_path) if scope_path else root/'config/round1.json'
    if not selected_scope.is_absolute():
        selected_scope = root/selected_scope
    scope = read_json(selected_scope)
    aggregation = read('aggregation_rules.json')
    for vid, variable in variables.items():
        require(bool(re.fullmatch(r'PV\d{2}', vid)), f'变量编码格式错误：{vid}')
        for field in ['name','higher_means','lower_means','interpretation_boundary']:
            require(isinstance(variable.get(field), str) and variable[field], f'{vid}缺少{field}')
    for iid, item in items.items():
        require(bool(re.fullmatch(r'[A-G]\d{2}', iid)), f'题目编码格式错误：{iid}')
        require(isinstance(item.get('text'), str) and item['text'], f'{iid}题目原文缺失')
        links = id_list(item.get('variable_ids'), iid+'.variable_ids')
        require(bool(links) and set(links).issubset(variables), f'{iid}引用未知变量')
        require(type(item.get('context_only')) is bool, f'{iid}背景标记必须为布尔值')
        require(item['context_only'] == iid.startswith('F'), f'{iid}与原设计F类背景标记不一致')
    for sid, scenario in scenarios.items():
        require(set(id_list(scenario.get('variable_ids'),sid+'.variable_ids')).issubset(variables), f'{sid}引用未知变量')
        require(set(id_list(scenario.get('item_ids'),sid+'.item_ids')).issubset(items), f'{sid}引用未知题目')
        if 'item_bindings' in scenario:
            raw_bindings = scenario['item_bindings']
            require(isinstance(raw_bindings, list), f'{sid}.item_bindings必须为数组')
            bound_ids = []
            for binding in raw_bindings:
                require(isinstance(binding, dict), f'{sid}题目绑定必须为对象')
                iid = binding.get('item_id')
                require(isinstance(iid, str) and iid in items, f'{sid}绑定了未知题目')
                require(not items[iid]['context_only'], f'{sid}核心绑定不能混入F类背景')
                targets = id_list(binding.get('target_variable_ids'), sid+'.target_variable_ids')
                require(bool(targets), f'{sid}/{iid}必须选择至少一个目标变量')
                require(set(targets).issubset(items[iid]['variable_ids']), f'{sid}/{iid}选择了题目原始映射之外的变量')
                require(set(targets).issubset(scenario['variable_ids']), f'{sid}/{iid}选择了情境范围之外的变量')
                require(isinstance(binding.get('use_condition'), str) and binding['use_condition'], f'{sid}/{iid}缺少使用条件')
                bound_ids.append(iid)
            require(len(bound_ids)==len(set(bound_ids)), f'{sid}含重复item_bindings')
            require(set(bound_ids)==set(scenario['item_ids']), f'{sid}.item_ids必须与item_bindings对应')
    require(scope.get('scenario_id') in scenarios, '当前情境ID不存在')
    active = id_list(scope.get('active_variable_ids'), 'active_variable_ids')
    core_items = id_list(scope.get('active_item_ids'), 'active_item_ids')
    context_items = id_list(scope.get('optional_context_item_ids'), 'optional_context_item_ids')
    require(bool(active) and set(active).issubset(variables), '本轮变量为空或包含未知变量')
    require(bool(core_items) and set(core_items).issubset(items), '本轮题目为空或包含未知题目')
    require(set(context_items).issubset(items), '背景题目不存在')
    require(set(active).issubset(scenarios[scope['scenario_id']]['variable_ids']), '本轮变量超出情境设计')
    require(set(core_items).issubset(scenarios[scope['scenario_id']]['item_ids']), '本轮题目超出情境已准备映射')
    require(all(not items[x]['context_only'] for x in core_items), '核心题目混入F类背景')
    require(all(items[x]['context_only'] for x in context_items), '背景列表混入核心题目')
    require(scope.get('risk_output_enabled') is False, '第一轮尚未实现风险评分，不能启用此开关')
    for rid, rule in rules.items():
        mapped = id_list(rule.get('item_ids'), rid+'.item_ids')
        require(bool(mapped) and set(mapped).issubset(items), f'{rid}题目映射无效')
        pv = rule.get('variable_id')
        require(pv in variables, f'{rid}引用未知变量')
        require(all(pv in items[i]['variable_ids'] for i in mapped), f'{rid}违反原题目—变量映射')
        require(rule.get('direction') in ['higher','lower','unclear'], f'{rid}方向无效')
        require(type(rule.get('context_only')) is bool, f'{rid}背景标记类型错误')
        require(all(items[i]['context_only'] == rule['context_only'] for i in mapped), f'{rid}背景标记不一致')
        for field in ['criterion','do_not_infer_when','review_status']:
            require(isinstance(rule.get(field), str) and rule[field], f'{rid}缺少{field}')
        # 全局规则库可含同一题的其他变量；运行时由allowed_rules精确选用，
        # 不因D04同时关联PV08而拒绝当前只选PV10的有效配置。
    expected = {'mode':'evidence_description_only','numeric_scores_enabled':False,
                'deduplicate_key':['event_id','variable_id','source_kind'],
                'missing_status':'insufficient_evidence','context_policy':'separate_only',
                'third_party_policy':'separate_only',
                'contradiction_policy':'retain_both_describe_as_mixed'}
    for key, value in expected.items():
        require(aggregation.get(key) == value and type(aggregation.get(key)) is type(value),
                f'aggregation_rules.{key}与当前已实现策略不一致；改变配置前需要相应代码支持')
    schemas = [read_json(root/'schemas'/name) for name in ['case.schema.json','extraction.schema.json']]
    for schema in schemas:
        check_schema(schema)
    config = Config(root, variables, items, scenarios, rules, scope, aggregation, *schemas)
    bindings = config.scenario_bindings()
    for iid in core_items:
        require(bool(set(bindings[iid]['target_variable_ids']) & set(active)), f'{iid}没有本轮启用的目标变量')
    return config
