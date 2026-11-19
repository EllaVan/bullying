import os
# pip install openai python-dotenv

from dotenv import load_dotenv
from openai import OpenAI

# python glm47_flash_demo.py


# 加载环境变量
load_dotenv()

def main():
    client = OpenAI(
        api_key=os.getenv("ZHIPU_API_KEY"),
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        # proxies=None,
    )

    # ---------------------- 普通对话调用 ----------------------
    resp = client.chat.completions.create(
        model="glm-4.7-flash",
        messages=[
            {"role": "system", "content": "你是资深Python算法工程师，回答简洁，代码优先。"},
            {"role": "user", "content": "写一段DTW时序对齐的简单python示例"}
        ],
        temperature=0.3, # 0~1，代码场景建议 0.2‑0.4；创意写作 0.7‑0.9
        max_tokens=128000, #最大输出长度，免费模型上限 128k，日常设 2048‑8192 即可
        stream=False # 流式，像 ChatGPT 一样逐字返回；False 一次性返回全部
    )
    print("===== 非流式返回 =====")
    print(resp.choices[0].message.content)

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
