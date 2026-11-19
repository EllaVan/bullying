import json
from .base_agent import BaseAgent

class EvidenceAgent(BaseAgent):
    def extract(self,conversation):
        prompt=f'''
从访谈中提取心理Evidence。
禁止诊断。
输出JSON数组:
[
{{"evidence_category":"","strength":0.0,"confidence":0.0}}
]
访谈:{conversation}
'''
        return json.loads(self.call_llm("Evidence抽取专家",prompt))
