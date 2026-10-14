"""LLM 多轮对话视图（P2 拆分）。

负责在可滚动结果区内渲染 AI 多轮对话：标题、用户/AI 消息气泡、
"AI 思考中..."加载态，以及底部追问输入行。业务状态（历史记录、
异步调度）由 DictionaryApp + LLMConversation 持有，本类只做纯视图。

气泡用原生 Label + wraplength 渲染：折行正确、高度贴合内容（无大片
空白）、行高由字体精确控制；在容器 resize 时统一刷新折行宽度。
"""

from tkinter import *
import re
from ui_constants import COLORS, FONTS, PAD


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

    def __init__(self, frame, on_resize, on_submit):
        self._frame = frame
        self._on_resize = on_resize
        self._on_submit = on_submit
        self._llm_input = None
        self._bubbles = []

        # 滚动容器宽度变化时刷新所有气泡折行宽度
        frame.bind("<Configure>", self._on_container_resize)

    @property
    def llm_input(self):
        return self._llm_input

    def _wrap_width(self):
        w = self._frame.winfo_width()
        return max(120, (398 if w <= 1 else w) - 24)

    def _on_container_resize(self, _event=None):
        wrap = self._wrap_width()
        for label in self._bubbles:
            label.config(wraplength=wrap)

    def render(self, history, loading):
        """整体重绘对话区。

        history: 对话历史（role/content 结构）；loading: 是否展示 AI 加载态。
        """
        latest = history[-1]["role"] if history else None

        for widget in self._frame.winfo_children():
            widget.destroy()
        self._bubbles = []

        Label(self._frame, text="AI 多轮对话（可继续追问）",
              font=FONTS["label_bold"], fg=COLORS["primary"]).pack(anchor=W, pady=(0, PAD["pad_l"]))

        wrap = self._wrap_width()
        for msg in history:
            role = msg["role"]
            bubble = Label(
                self._frame,
                text=(msg["content"] if role == "user"
                      else _markdown_to_plain(msg["content"])),
                font=FONTS["body"],
                fg=(COLORS["bubble_user_text"] if role == "user" else COLORS["bubble_ai_text"]),
                bg=(COLORS["bubble_user"] if role == "user" else COLORS["bubble_ai"]),
                wraplength=wrap,
                justify=(LEFT if role == "user" else LEFT),
                anchor=(E if role == "user" else W),
                padx=12, pady=8,
            )
            bubble.pack(fill=X, anchor=E if role == "user" else W, pady=PAD["pad_xs"])
            self._bubbles.append(bubble)

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