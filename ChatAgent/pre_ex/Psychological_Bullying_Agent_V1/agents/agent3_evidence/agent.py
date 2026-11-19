
import json
from models.llm_client import call_llm
from .prompt import SYSTEM_PROMPT


class EvidenceAgent:

    def extract(self,scenario,answer):

        result=call_llm(
            SYSTEM_PROMPT,
            json.dumps({
                "scenario":scenario,
                "answer":answer
            },ensure_ascii=False)
        )

        return json.loads(result)
