import os

from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()

def main():
    client = OpenAI(
        api_key=os.getenv("ZHIPU_API_KEY"),
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        # proxies=None,
    )

    # ---------------------- 流式输出（适合VSCode/终端实时打印） ----------------------
    print("\n===== 流式返回 =====")
    stream_resp = client.chat.completions.create(
        model="glm-4.7-flash",
        messages=[
            {"role": "system", "content": "你是资深Python算法工程师，回答简洁，代码优先。"},
            {"role": "user", "content": "简单解释对比损失温度系数作用"}
        ],
        temperature=0.3,
        max_tokens=1024,
        stream=True
    )
    for chunk in stream_resp:
        delta = chunk.choices[0].delta
        if delta.content:
            print(delta.content, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
