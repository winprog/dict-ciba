"""LLM 多轮对话视图（P2 拆分）。

负责在可滚动结果区内渲染 AI 多轮对话：标题、用户/AI 消息气泡、
"AI 思考中..."加载态，以及底部追问输入行。业务状态（历史记录、
异步调度）由 DictionaryApp + LLMConversation 持有，本类只做纯视图。

气泡用只读 SelectableText 渲染：支持鼠标划选复制，折行/高度贴合由
控件自身随容器宽度自适应，不需统一刷新折行宽度。
"""

from tkinter import *
import re
from ui.ui_constants import COLORS, FONTS, PAD
from ui.selectable_text import SelectableText
from ui.markdown_blocks import split_blocks
from ui.table_widget import TableWidget


def _markdown_to_plain(text: str) -> str:
    """把 LLM 返回的轻量 markdown 降为纯文本（保留段落与列表结构）。"""
    # 去掉加粗/斜体的星号标记
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # 去掉标题井号
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    # 无序列表符号统一
    text = re.sub(r"^[ \t]*[-*+]\s+", "• ", text, flags=re.M)
    return text


class LLMChatView:
    """渲染 LLM 多轮对话历史与追问输入行。"""

    def __init__(self, frame, on_resize, on_submit, on_export_summary=None):
        self._frame = frame
        self._on_resize = on_resize
        self._on_submit = on_submit
        self._on_export_summary = on_export_summary
        self._summary_btn = None
        self._llm_input = None
        self._latest_answer = None
        self._latest_question = None

    @property
    def summary_btn(self):
        """顶部「导出对话总结」按钮（供调用方切换禁用/文案）。"""
        return self._summary_btn

    @property
    def llm_input(self):
        return self._llm_input

    @property
    def latest_answer_widget(self):
        """最后一个 AI 回答气泡（供调用方把视口定位到回答开头）。"""
        return self._latest_answer

    @property
    def latest_question_widget(self):
        """最后一轮追问的用户问题气泡（供视口定位，让问题与回答开头一起可见）。"""
        return self._latest_question

    def render(self, history, loading):
        """整体重绘对话区。

        history: 对话历史（role/content 结构）；loading: 是否展示 AI 加载态。
        """
        latest = history[-1]["role"] if history else None

        for widget in self._frame.winfo_children():
            widget.destroy()

        head = Frame(self._frame)
        head.pack(fill=X, pady=(0, PAD["pad_l"]))
        Label(head, text="AI 多轮对话（可继续追问）",
              font=FONTS["label_bold"], fg=COLORS["primary"]).pack(anchor=W, side=LEFT)
        self._summary_btn = Button(
            head, text="导出对话总结",
            command=self._on_export_summary or (lambda: None),
            bg=COLORS["primary"], fg=COLORS["primary_text_on"],
            font=FONTS["small"], relief=FLAT, cursor="hand2",
        )
        self._summary_btn.pack(side=RIGHT)

        self._latest_answer = None
        self._latest_question = None
        for msg in history:
            role = msg["role"]
            if role == "user":
                bubble = SelectableText(
                    self._frame,
                    msg["content"],
                    font=FONTS["body"],
                    fg=COLORS["bubble_user_text"],
                    bg=COLORS["bubble_user"],
                    pad=8,
                )
                bubble.pack(fill=X, anchor=E, pady=PAD["pad_xs"])
                self._latest_question = bubble
            else:
                last = None
                for block in split_blocks(msg["content"]):
                    if block.kind == "text":
                        last = SelectableText(
                            self._frame,
                            _markdown_to_plain(block.content),
                            font=FONTS["body"],
                            fg=COLORS["bubble_ai_text"],
                            bg=COLORS["bubble_ai"],
                            pad=8,
                        )
                        last.pack(fill=X, anchor=W, pady=PAD["pad_xs"])
                    else:
                        last = TableWidget(
                            self._frame, header=block.header, rows=block.rows,
                        )
                        last.pack(fill=X, anchor=W, pady=PAD["pad_xs"])
                self._latest_answer = last

        if loading and latest == "user":
            Label(self._frame, text="AI 思考中...",
                  font=FONTS["italic"], fg=COLORS["text_disabled"]).pack(anchor=W, pady=PAD["pad_xs"])

        self._render_followup_input()
        self._frame.update_idletasks()
        self._on_resize()

    def _render_followup_input(self):
        """渲染底部追问输入行（回车或点击"追问"提交）。"""
        row = Frame(self._frame)
        row.pack(fill=X, pady=(PAD["pad_lg"], 0))

        self._llm_input = Entry(row, font=FONTS["input"])
        self._llm_input.pack(side=LEFT, fill=X, expand=True, padx=(0, PAD["pad_m"]))
        self._llm_input.bind("<Return>", lambda e: self._on_submit())

        ask_btn = Button(row, text="追问", command=self._on_submit,
                         bg=COLORS["primary"], fg=COLORS["primary_text_on"],
                         font=FONTS["small"], relief=FLAT, cursor="hand2")
        ask_btn.pack(side=RIGHT)

        self._llm_input.focus_set()