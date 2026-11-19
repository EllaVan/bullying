
import json
from models.llm_client import call_llm
from .prompt import SYSTEM_PROMPT


class InterviewAgent:

    def chat(self,scenario,answer,history):

        result=call_llm(
            SYSTEM_PROMPT,
            json.dumps({
                "scenario":scenario,
                "answer":answer,
                "history":history
            },ensure_ascii=False)
        )

        return json.loads(result)
