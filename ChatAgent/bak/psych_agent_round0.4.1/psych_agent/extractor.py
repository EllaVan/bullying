"""A3只构造测量上下文并调用适配器；不读取fixtures或reference_annotations。"""
import json
from copy import deepcopy

from .evidence import validate_case
from .llm_client import call_chat


def build_messages(case, cfg):
    validate_case(case, cfg)
    rules = list(cfg.allowed_rules().values())
    active = list(cfg.scope['active_variable_ids'])
    background = sorted({r['variable_id'] for r in rules if r['context_only']} - set(active))
    fields = ['variable_id','name','higher_means','lower_means','interpretation_boundary']
    variables = [{key:cfg.variables[vid][key] for key in fields} for vid in active]
    context_variables = [{key:cfg.variables[vid][key] for key in fields} for vid in background]
    # 通用schema保留在文件中；每次请求按当前scope生成gaps枚举，不写死S01变量。
    output_schema = deepcopy(cfg.extraction_schema)
    output_schema['properties']['gaps']['items']['properties']['variable_id']['enum'] = list(active)
    iids = cfg.scope['active_item_ids'] + cfg.scope['optional_context_item_ids']
    bindings = cfg.scenario_bindings()
    items = []
    for iid in iids:
        item = cfg.items[iid]
        binding = bindings.get(iid)
        targets = ([v for v in binding['target_variable_ids'] if v in cfg.scope['active_variable_ids']]
                   if binding else [])
        items.append({'item_id':iid,'text':item['text'],'source_variable_ids':item['variable_ids'],
                      'target_variable_ids':targets,'context_only':item['context_only'],
                      'use_condition':binding['use_condition'] if binding else '仅保存自发出现的背景信息。'})
    measurement = {'active_variable_ids':active, 'gaps_allowed_variable_ids':list(active),
                   'variables':variables,'context_variables':context_variables,
                   'items':items,'evidence_rules':rules,'output_schema':output_schema}
    system = (cfg.root/'prompts/evidence_extractor.md').read_text(encoding='utf-8')
    system += '\n\n以下是本轮只读测量配置：\n' + json.dumps(measurement,ensure_ascii=False)
    # 把回答作为user数据，决不拼接到system指令区。
    return [{'role':'system','content':system},
            {'role':'user','content':'请仅分析以下实验记录中的学生answer：\n'+json.dumps(case,ensure_ascii=False)}]


def extract_text(case, cfg, settings, client=call_chat):
    return client(build_messages(case,cfg),settings)
