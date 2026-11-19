
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
        api_key=os.getenv("ZHIPU_API_KEY"),
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        # proxies=None,
    )
MODEL="glm-4.7-flash",

def call_llm(system,payload):
    r=client.chat.completions.create(
        model="glm-4.7-flash",
        temperature=0.2,
        response_format={"type":"json_object"},
        messages=[
        {"role":"system","content":system},
        {"role":"user","content":payload}
        ])
    return r.choices[0].message.content
