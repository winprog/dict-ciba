"""LLM 对话总结导出工具。

把多轮问答交给 LLM 做总结，并写入当前项目下某个本地工作目录（默认
exports/，该目录已被 .gitignore 排除，不会提交进仓库）。

chat 参数在 GUI 中注入 services.llm_client.chat_messages；纯逻辑部分
（build_summary_messages / export_summary）可在单测中用假 chat 驱动，
不触网。
"""
import os
from datetime import datetime

SUMMARY_SYSTEM_PROMPT = (
    "你是一个严谨的文字总结助手。请对用户给出的多轮问答记录做精炼、有条理"
    "的中文总结，保留关键结论与重要细节，输出为 markdown。"
)

DEFAULT_OUT_DIR_ENV = "DICT_LLM_SUMMARY_DIR"


def build_summary_messages(history):
    """把对话历史组织成一条要求 LLM 做总结的 user 消息数组。"""
    if history:
        body = "\n\n".join(f"[{m['role']}] {m['content']}" for m in history)
    else:
        body = "(空对话)"
    content = "请对以下多轮问答做总结：\n\n" + body
    return [{"role": "user", "content": content}]


def export_summary(text, out_dir):
    """把总结文本写入 out_dir 下的带时间戳 md 文件，返回绝对路径。"""
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"llm_summary_{ts}.md")
    payload = (
        f"# LLM 对话总结\n\n"
        f"_导出时间：{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:15]}_\n\n"
        f"---\n\n{text}\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(payload)
    return os.path.abspath(path)


def request_summary(history, chat, out_dir):
    """调用 LLM 总结历史问答并落盘，返回 (summary, absolute_path)。"""
    messages = build_summary_messages(history)
    summary = chat(messages, system_prompt=SUMMARY_SYSTEM_PROMPT).strip()
    path = export_summary(summary, out_dir)
    return summary, path