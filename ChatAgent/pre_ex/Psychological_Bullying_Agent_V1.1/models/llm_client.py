
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
        api_key=os.getenv("ZHIPU_API_KEY"),
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        # proxies=None,
    )

def call_llm(system,user):
    r=client.chat.completions.create(
        model="glm-4.7-flash",
        temperature=0.3,
        response_format={"type":"json_object"},
        messages=[
            {"role":"system","content":system},
            {"role":"user","content":user}
        ]
    )
    return r.choices[0].message.content
