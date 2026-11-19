
import json
from models.llm_client import call_llm
from .prompt import SYSTEM_PROMPT


class ScenarioAgent:

    def generate(self,target_variables):

        result = call_llm(
            SYSTEM_PROMPT,
            json.dumps({
                "variables":target_variables
            },ensure_ascii=False)
        )

        return json.loads(result)
