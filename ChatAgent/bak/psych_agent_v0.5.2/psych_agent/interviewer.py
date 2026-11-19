"""A2：表达控制器选择的当前目标，不自行添加变量、情境事实或评分。"""


class TemplateInterviewer:
    def ask(self, task, history):
        return {'question':task['question_template']}


class LLMInterviewer:
    def __init__(self, cfg, transport):
        self.cfg, self.transport = cfg, transport

    def ask(self, task, history):
        system=(self.cfg.root/'prompts/interviewer.md').read_text(encoding='utf-8')
        # A2仅接收表达所需的目标、事实和对话；风险结果及全部证据规则不进入上下文。
        visible = {k:task[k] for k in ('task_id','mode','scenario_text','facts','target_unit_id',
                   'reference_frame','question_template','missing_slots','already_covered')}
        if task['target_unit_id']:
            unit=next(u for u in task['allowed_units'] if u['unit_id']==task['target_unit_id'])
            visible['target']={k:unit[k] for k in ('facet','reference_frame','required_slots','interpretation_boundary')}
        dialogue=[{'question':t['question'],'answer':t['answer']} for t in history]
        return self.transport.request(system,{'task':visible,'history':dialogue},task['task_id'])
