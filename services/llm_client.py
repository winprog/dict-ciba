import os
import sys
import json
import requests

DEFAULT_BASE_URL = "https://modelapi-test.haier.net/model/v1"
DEFAULT_MODEL = "Qwen3.6-35B-A3B"


def _system_prompt_default():
    return "你是一个中英文语言理解助手，能解释单词、短语、句子和段落，并支持多轮追问和深入解释。"


def _chat(messages, model=None):
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

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"]


def chat_messages(messages: list, system_prompt: str = None, model: str = None) -> str:
    """投递完整消息数组（含对话历史），用于多轮追问。

    messages: [{"role": "user"/"assistant", "content": str}, ...]
    """
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + list(messages)
    return _chat(messages, model)


def chat(prompt: str, system_prompt: str = None, model: str = None, history: list = None) -> str:
    """单轮/带历史对话。history 为已有的 (user/assistant) 消息数组，会追加在 prompt 之前。"""
    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    return chat_messages(messages, system_prompt, model)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python llm_client.py <prompt>")
        print("  LLM_API_KEY=xxx python llm_client.py '你好'")
        sys.exit(1)

    result = chat(sys.argv[1])
    print(result)