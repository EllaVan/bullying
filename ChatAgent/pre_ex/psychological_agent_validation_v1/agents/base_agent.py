from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

class BaseAgent:
    def __init__(self):
        self.client=OpenAI(api_key=os.getenv("API_KEY"))
        self.model=os.getenv("MODEL","glm-4.7-flas")
    
    def call_llm(self,system,user):
        r=self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role":"system","content":system},
                {"role":"user","content":user}
            ],
            temperature=0.2
        )
        return r.choices[0].message.content
