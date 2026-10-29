"""LLM 对话总结（summary_exporter）的单元测试。

覆盖：总结 prompt 组装、导出文件落盘与路径、request_summary 用假 chat
把总结写出（不触网）。
"""
import os

from services.summary_exporter import (
    build_summary_messages,
    export_summary,
    request_summary,
    SUMMARY_SYSTEM_PROMPT,
)


def test_build_summary_messages_packs_history():
    history = [
        {"role": "user", "content": "什么是 transformer？"},
        {"role": "assistant", "content": "是一种自注意力架构。"},
    ]
    msgs = build_summary_messages(history)
    assert len(msgs) == 1 and msgs[0]["role"] == "user"
    assert "transformer" in msgs[0]["content"]
    assert "assistant" in msgs[0]["content"]
    assert "自注意力" in msgs[0]["content"]


def test_export_summary_writes_md_file(tmp_path):
    out_dir = str(tmp_path / "exports")
    path = export_summary("这是总结内容。", out_dir)
    assert path.endswith(".md") and os.path.isabs(path)
    assert os.path.dirname(path) == os.path.abspath(out_dir)
    with open(path, encoding="utf-8") as f:
        body = f.read()
    assert "# LLM 对话总结" in body
    assert "这是总结内容。" in body


def test_request_summary_uses_fake_chat_and_writes(tmp_path):
    calls = {}

    def fake_chat(messages, system_prompt=None):
        calls["messages"] = messages
        calls["system_prompt"] = system_prompt
        return "  总结正文民  "

    history = [{"role": "user", "content": "Q1"}]
    summary, path = request_summary(history, fake_chat, str(tmp_path / "o"))
    assert summary == "总结正文民"          # 已 strip
    assert calls["system_prompt"] == SUMMARY_SYSTEM_PROMPT
    assert calls["messages"][0]["role"] == "user"
    assert os.path.exists(path)