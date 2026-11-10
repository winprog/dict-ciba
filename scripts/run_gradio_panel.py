#!/usr/bin/env python3
"""启动 Gradio 模型驱动 LLM 面板（原型入口）。

用法：source env.sh && python scripts/run_gradio_panel.py [初始词]

启动本地 Gradio server（127.0.0.1:7860），传入捕获词作为首轮用户消息，
并自动弹出本机浏览器进行模型交互。与 Tk 取词终端解耦，仅作手感验证。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.gradio_panel import launch_panel, with_formula_hint  # noqa: E402
from services.llm_client import chat_messages as llm_chat_messages  # noqa: E402

SYSTEM_PROMPT = with_formula_hint(
    (
        "你是一个中英文语言理解助手，能解释单词、短语、句子和段落，"
        "并支持多轮追问和深入解释。可用 markdown 排版回答（含表格）。\n"
        "回答请始终使用简体中文；仅专有名词、代码、数学公式可保留原文/原样。\n"
        "原文若夹杂非常用分隔/装饰字符（如 ♣、✦、❀ 等花纹类符号），请一律忽略、"
        "仅视作分段，必须完整翻译或作答全文，不得从中途截断省略。"
    )
)


def main():
    initial_word = sys.argv[1] if len(sys.argv) > 1 else "你好"
    demo, url = launch_panel(
        initial_word=initial_word,
        chat=llm_chat_messages,
        system_prompt=SYSTEM_PROMPT,
        port=7860,
        in_browser=True,
    )
    print(f"面板已启动: {url}")
    return demo


if __name__ == "__main__":
    main()