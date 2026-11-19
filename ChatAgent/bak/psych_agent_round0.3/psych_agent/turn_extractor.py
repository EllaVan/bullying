"""多轮A3适配器；旧 extractor.py 的单案例接口继续独立使用。"""
from .dialogue_contracts import observation_schema


class LLMTurnExtractor:
    def __init__(self, cfg, transport):
        self.cfg, self.transport = cfg, transport

    def extract(self, task, turn, history):
        system=(self.cfg.root/'prompts/turn_extractor.md').read_text(encoding='utf-8')
        rules=sorted({r for u in task['allowed_units'] for r in u['rule_ids']})
        units=task['allowed_units']
        vids=sorted({v for u in units for v in u['target_variable_ids']})
        payload={'scenario':{'text':task['scenario_text'],'facts':task['facts'],'condition_id':task['condition_id']},
                 'current_turn':turn,
                 'history':[{'turn_id':t['turn_id'],'question':t['question'],'answer':t['answer']} for t in history],
                 'allowed_units':units,'rules':[self.cfg.rules[r] for r in rules],
                 'variables':[self.cfg.base.variables[v] for v in vids],
                 'source_items':[self.cfg.base.items[i] for i in sorted({i for u in units for i in u['source_item_ids']})],
                 'background_items':[self.cfg.base.items[i] for i in ('F01','F02','F03','F04')],
                 'output_schema':observation_schema([u['unit_id'] for u in units], rules)}
        return self.transport.request(system,payload,task['task_id'])
