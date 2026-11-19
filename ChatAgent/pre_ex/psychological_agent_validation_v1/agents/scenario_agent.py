import json
from .base_agent import BaseAgent

class ScenarioAgent(BaseAgent):
    def generate(self,target_variables,assessment_goal=None):
        prompt=f'''
根据心理变量生成校园互动情境。
目标变量:{target_variables}
不要使用霸凌标签。
输出JSON:
{{"scenario_text":"","questions":[]}}
'''
        return json.loads(self.call_llm("情境设计专家",prompt))
