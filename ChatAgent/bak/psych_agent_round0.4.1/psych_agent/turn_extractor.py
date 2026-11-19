"""多轮A3适配器；旧 extractor.py 的单案例接口继续独立使用。"""
from .dialogue_contracts import observation_schema, validate_turn
from .io_utils import ValidationError


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
        candidate=self.transport.request(system,payload,task['task_id'])
        try:
            # A3在返回编排器前先执行与最终提交完全相同的只读校验。
            # 校验不会修改状态，成功结果仍会由MeasurementController再次校验后提交。
            validate_turn(task,turn,history,candidate,self.cfg)
            return candidate
        except ValidationError as first_error:
            repair_system=(self.cfg.root/'prompts/turn_repair.md').read_text(encoding='utf-8')
            repair_payload={'validation_error':str(first_error),'invalid_output':candidate,
                            'original_request':payload,'output_schema':payload['output_schema']}
            repaired=self.transport.request(repair_system,repair_payload,task['task_id'])
            try:
                validate_turn(task,turn,history,repaired,self.cfg)
            except ValidationError as repair_error:
                raise ValidationError(f'A3结构修复后仍不符合契约：{repair_error}') from repair_error
            return repaired
