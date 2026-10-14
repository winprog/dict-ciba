"""LLM 多轮对话视图（P2 拆分）。

负责在可滚动结果区内渲染 AI 多轮对话：标题、用户/AI 消息气泡、
"AI 思考中..."加载态，以及底部追问输入行。业务状态（历史记录、
异步调度）由 DictionaryApp + LLMConversation 持有，本类只做纯视图。

构造需传入滚动容器 frame、布局完成后触发的回调 on_resize，以及
用户点击 "追问"/回车时的提交回调 on_submit（App 授权的权威逻辑）。
"""

from tkinter import *
import html
import markdown
from tkinterweb import HtmlFrame
from ui_constants import COLORS, FONTS, PAD


class LLMChatView:
    """渲染 LLM 多轮对话历史与追问输入行。"""

    def __init__(self, frame, on_resize, on_submit):
        self._frame = frame
        self._on_resize = on_resize
        self._on_submit = on_submit
        self._llm_input = None

    @property
    def llm_input(self):
        return self._llm_input

    def render(self, history, loading):
        """整体重绘对话区。

        history: 对话历史（role/content 结构）；loading: 是否展示 AI 加载态。
        """
        latest = history[-1]["role"] if history else None

        for widget in self._frame.winfo_children():
            widget.destroy()

        Label(self._frame, text="AI 多轮对话（可继续追问）",
              font=FONTS["label_bold"], fg=COLORS["primary"]).pack(anchor=W, pady=(0, PAD["pad_l"]))

        for msg in history:
            role = msg["role"]
            content = msg["content"]
            bubble = self._chat_bubble_html(
                markdown.markdown(content) if role != "user" else content,
                user=(role == "user"),
            )
            viewer = HtmlFrame(self._frame, scrollbar=False,
                               messages_are_links=True, contextmenu=False,
                               highlight_words=False)
            viewer.load_html(bubble)
            viewer.pack(fill=X, anchor=E if role == "user" else W, pady=PAD["pad_xs"])

        if loading and latest == "user":
            Label(self._frame, text="AI 思考中...",
                  font=FONTS["italic"], fg=COLORS["text_disabled"]).pack(anchor=W, pady=PAD["pad_xs"])

        self._render_followup_input()
        self._frame.update_idletasks()
        self._on_resize()

    def _chat_bubble_html(self, content: str, user: bool):
        """把对话内容包成统一气泡样式的 HTML。"""
        esc = html.escape(content).replace("\n", "<br>")
        if user:
            style = (f"background:{COLORS['bubble_user']}; color:{COLORS['bubble_user_text']};"
                     "padding:8px 12px; border-radius:6px; text-align:left;")
        else:
            style = (f"background:{COLORS['bubble_ai']}; color:{COLORS['bubble_ai_text']};"
                     "padding:8px 12px; border-radius:6px;")
        return f'<div style="{style}">{esc}</div>'

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