
import json
from models.llm_client import call_llm
from .prompt import SYSTEM_PROMPT


class ReasoningAgent:

    def reason(self,evidence):

        result=call_llm(
            SYSTEM_PROMPT,
            json.dumps(evidence,ensure_ascii=False)
        )

        return json.loads(result)
