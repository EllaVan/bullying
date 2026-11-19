"""A1：测量任务的情境实例化。事实由蓝图规定，Agent只能组织叙述。"""
from copy import deepcopy

from .config import require
from .dialogue_config import digest, exact_keys


def build_scenario_task(cfg, entry, session_id, index):
    condition = cfg.condition(entry)
    sid = entry['scenario_id']
    return {'scenario_id':sid,'condition_id':entry['condition_id'],
            'parent_condition_id':condition['parent_condition_id'],
            'scenario_instance_id':f'{session_id}_{index+1:02d}_{sid}_{entry["condition_id"]}',
            'event_id':'SCENE_'+digest([session_id,sid])[:16],
            'facts':condition['facts'],'template_text':condition['text'],
            'measurement_units':list(cfg.unit_views(entry).values()),
            'source_items':[cfg.base.items[i] for i in entry['active_item_ids']]}


def freeze_scenario(task, output):
    exact_keys(output, ['text','facts'], 'A1输出')
    require(output['facts'] == task['facts'], 'A1改变了蓝图固定事实；条件变化须进入预先配置的条件分支')
    require(isinstance(output['text'],str) and output['text'].strip() and len(output['text'])<=4000, 'A1情境文本无效或过长')
    result = {k:deepcopy(task[k]) for k in ('scenario_id','condition_id','parent_condition_id','scenario_instance_id','event_id','facts')}
    result['text'] = output['text'].strip()
    result['instance_hash'] = digest(result)
    return result


class TemplateScenarioGenerator:
    def generate(self, task):
        return {'text':task['template_text'],'facts':deepcopy(task['facts'])}


class LLMScenarioGenerator:
    def __init__(self, cfg, transport):
        self.cfg, self.transport = cfg, transport

    def generate(self, task):
        system=(self.cfg.root/'prompts/scenario_generator.md').read_text(encoding='utf-8')
        return self.transport.request(system,task,task['scenario_instance_id'])
