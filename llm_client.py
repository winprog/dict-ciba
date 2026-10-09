import os
import sys
import json
import requests

DEFAULT_BASE_URL = "https://modelapi-test.haier.net/model/v1"
DEFAULT_MODEL = "Qwen3.6-35B-A3B"


def chat(prompt: str, system_prompt: str = None, model: str = None) -> str:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL
    model = model or os.environ.get("LLM_MODEL") or DEFAULT_MODEL

    if not api_key:
        raise RuntimeError(
            "未找到 API Key，请设置环境变量 LLM_API_KEY 或 OPENAI_API_KEY"
        )

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python llm_client.py <prompt>")
        print("  LLM_API_KEY=xxx python llm_client.py '你好'")
        sys.exit(1)

    result = chat(sys.argv[1])
    print(result)