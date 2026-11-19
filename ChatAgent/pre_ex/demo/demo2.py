import os
import requests
import json
from dotenv import load_dotenv

# curl https://open.bigmodel.cn/api/paas/v4/chat/completions \
# -H "Authorization: Bearer sk-你的key" \
# -H "Content-Type: application/json" \
# -d '{
#   "model":"glm-4.7-flash",
#   "messages":[{"role":"user","content":"hello"}],
#   "temperature":0.3,
#   "max_tokens":512,
#   "stream":false
# }'


load_dotenv()

API_KEY = os.getenv("ZHIPU_API_KEY")
BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def normal_chat():
    """非流式：一次性获取完整结果"""
    payload = {
        "model": "glm-4.7-flash",
        "messages": [
            {"role": "system", "content": "你是资深算法工程师，回答简洁，优先给出代码。"},
            {"role": "user", "content": "写一个简单DTW时序对齐Python示例"}
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
        "stream": False
    }

    resp = requests.post(BASE_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    print("===== 非流式响应 =====")
    print(content)


def stream_chat():
    """SSE流式输出，逐字打印"""
    payload = {
        "model": "glm-4.7-flash",
        "messages": [
            {"role": "system", "content": "你是资深算法工程师，回答简洁。"},
            {"role": "user", "content": "解释对比损失温度系数的作用"}
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
        "stream": True
    }

    print("\n===== 流式响应 =====")
    with requests.post(BASE_URL, headers=headers, json=payload, stream=True, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            # SSE格式 data: {...}
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0]["delta"]
                    if "content" in delta and delta["content"]:
                        print(delta["content"], end="", flush=True)
                except json.JSONDecodeError:
                    continue
    print()


if __name__ == "__main__":
    normal_chat()
    stream_chat()
