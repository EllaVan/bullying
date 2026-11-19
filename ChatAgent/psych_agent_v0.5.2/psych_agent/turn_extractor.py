"""多轮A3适配器；旧 extractor.py 的单案例接口继续独立使用。"""
from copy import deepcopy

from .dialogue_contracts import observation_schema, validate_turn
from .io_utils import ValidationError


class LLMTurnExtractor:
    def __init__(self, cfg, transport):
        self.cfg, self.transport = cfg, transport
        self.last_diagnostic = None

    @staticmethod
    def _normalize_context_references(candidate, task, history):
        """只删除不可能成立的上下文引用，不补写观察、原话或证据。"""
        normalized = deepcopy(candidate)
        valid = {row['turn_id'] for row in history
                 if row.get('scenario_instance_id') == task['scenario_instance_id']}
        removed = []
        observations = normalized.get('observations') if isinstance(normalized, dict) else None
        if not isinstance(observations, list):
            return normalized, removed
        for index, observation in enumerate(observations):
            if not isinstance(observation, dict) or not isinstance(observation.get('context_turn_ids'), list):
                continue
            kept = []
            for turn_id in observation['context_turn_ids']:
                if turn_id in valid and turn_id not in kept:
                    kept.append(turn_id)
                else:
                    removed.append({'observation_index':index, 'turn_id':turn_id})
            observation['context_turn_ids'] = kept
        return normalized, removed

    def extract(self, task, turn, history):
        self.last_diagnostic = None
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
        raw_candidate=self.transport.request(system,payload,task['task_id'])
        candidate, removed = self._normalize_context_references(raw_candidate, task, history)
        try:
            # A3在返回编排器前先执行与最终提交完全相同的只读校验。
            # 校验不会修改状态，成功结果仍会由MeasurementController再次校验后提交。
            validate_turn(task,turn,history,candidate,self.cfg)
            if removed:
                self.last_diagnostic={'status':'normalized_context_references',
                                      'removed_context_references':removed,
                                      'fallback_used':False}
            return candidate
        except ValidationError as first_error:
            repair_system=(self.cfg.root/'prompts/turn_repair.md').read_text(encoding='utf-8')
            repair_payload={'validation_error':str(first_error),'invalid_output':candidate,
                            'original_request':payload,'output_schema':payload['output_schema']}
            raw_repaired=self.transport.request(repair_system,repair_payload,task['task_id'])
            repaired, repaired_removed = self._normalize_context_references(raw_repaired, task, history)
            try:
                validate_turn(task,turn,history,repaired,self.cfg)
            except ValidationError as repair_error:
                # 模型的结构错误不能中断测量，也不能通过臆造证据来掩盖。
                # 空观察是协议允许的保守降级；控制器会记录本轮信息不足并继续流程。
                fallback={'turn_id':turn['turn_id'],'observations':[],'background':[]}
                validate_turn(task,turn,history,fallback,self.cfg)
                self.last_diagnostic={'status':'safe_empty_fallback',
                                      'first_validation_error':str(first_error),
                                      'repair_validation_error':str(repair_error),
                                      'removed_context_references':removed+repaired_removed,
                                      'fallback_used':True}
                return fallback
            self.last_diagnostic={'status':'llm_repair_succeeded',
                                  'first_validation_error':str(first_error),
                                  'removed_context_references':removed+repaired_removed,
                                  'fallback_used':False}
            return repaired
