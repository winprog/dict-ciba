"""顶层 UI 装配（AppLayoutBuilder，P2 拆分收尾）。

把 DictionaryApp.__init__ 中"顶栏操作面板 + 输入面板"的控件创建，
及这些控件的状态刷新行为（按钮文字/颜色/状态灯切换）收口为一个
MainView。

设计目标——减少属性回传：App 不再直接持有并 config 一堆裸按钮，
而是调用 MainView 提供的"行为方法"（如 refresh_capture /
set_topmost_mode / set_hide_state），让视觉状态变化内聚在本文件；
App 只通过 bind_actions 注入需要触发的业务回调。
"""

from tkinter import *
from tkinter import ttk
from services.search_history import SearchHistory
from ui.ui_constants import COLORS, FONTS, PAD


class MainView:
    """聚合窗口顶部操作与输入两栏的视图。

    面板分组：self.top（操作区）、self.search（输入区）。
    控件同时以扁平属性暴露（self.capture_btn 等），与既有引用语义一致。
    """

    def __init__(self, root):
        self.root = root

        # 顶部操作面板
        self.top = Frame(root, pady=PAD["pad_s"])
        self.top.pack(fill=X)
        self._build_top_panel()

        # 搜索输入面板
        self.search = Frame(root, pady=PAD["pad_md"])
        self.search.pack(fill=X)
        self._build_input_panel()

    # ---------- 构建：面板分组 ----------
    def _build_top_panel(self):
        """顶栏：取词状态灯 + 取词按钮 + 状态标签 + 悬停选项 + 置顶/隐藏。"""
        # 取词状态灯（绿点亮 = 取词运行中）
        self.capture_led = Canvas(self.top, width=12, height=12,
                                  highlightthickness=0, bg=self.root.cget("bg"))
        self._led_item = self.capture_led.create_oval(
            2, 2, 10, 10, fill=COLORS["text_disabled"], outline="")
        self.capture_led.pack(side=LEFT, padx=(PAD["pad_md"], PAD["pad_xs"]))

        # 取词模式按钮（command 由 bind_actions 绑定）
        self.capture_btn = Button(self.top, text="启动取词模式",
                                  bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"],
                                  font=FONTS["caption"])
        self.capture_btn.pack(side=LEFT, padx=PAD["pad_md"])

        # 状态标签
        self.status_label = Label(self.top, text="取词模式: 关闭",
                                  font=FONTS["caption"], fg=COLORS["text_secondary"])
        self.status_label.pack(side=LEFT, padx=PAD["pad_md"])

        # 鼠标悬停取词选项（默认禁用）
        self.enable_hover_var = BooleanVar(value=False)
        self.hover_check = Checkbutton(self.top, text="启用鼠标悬停取词",
                                       variable=self.enable_hover_var,
                                       font=FONTS["caption"])
        self.hover_check.pack(side=LEFT, padx=PAD["pad_md"])

        # 置顶按钮（右侧）
        self.window_btn = Button(self.top, text="置顶显示",
                                 bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"],
                                 font=FONTS["caption"])
        self.window_btn.pack(side=RIGHT, padx=PAD["pad_s"])

        # 隐藏按钮（右侧）
        self.hide_btn = Button(self.top, text="隐藏窗口",
                               bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"],
                               font=FONTS["caption"])
        self.hide_btn.pack(side=RIGHT, padx=PAD["pad_s"])

    def _build_input_panel(self):
        """输入栏：搜索历史 Combobox + Search + LLM 按钮。"""
        # P3-4 搜索历史（最近 20 条，JSON 持久化）
        self.history = SearchHistory()
        self.entry = ttk.Combobox(self.search, font=FONTS["input"],
                                  values=self.history.list())
        self.entry.pack(side=LEFT, fill=X, expand=True,
                        padx=(PAD["pad_md"], PAD["pad_s"]))

        self.btn = Button(self.search, text="Search",
                          font=FONTS["small"], relief=FLAT,
                          bg=COLORS["primary"], fg=COLORS["primary_text_on"])
        self.btn.pack(side=RIGHT, padx=(PAD["pad_s"], 0))

        self.llm_btn = Button(self.search, text="LLM",
                              font=FONTS["small"], relief=FLAT,
                              bg=COLORS["primary"], fg=COLORS["primary_text_on"])
        self.llm_btn.pack(side=RIGHT, padx=(0, PAD["pad_md"]))

    # ---------- 行为绑定 ----------
    def bind_actions(self, actions):
        """把业务回调绑定到各控件。

        actions 期望键：
          toggle_capture / toggle_hover / toggle_topmost / hide /
          search / search_llm
        """
        self.capture_btn.config(command=actions["toggle_capture"])
        self.hover_check.config(command=actions["toggle_hover"])
        self.window_btn.config(command=actions["toggle_topmost"])
        self.hide_btn.config(command=actions["hide"])
        self.btn.config(command=actions["search"])
        self.llm_btn.config(command=actions["search_llm"])

        self.entry.bind("<Return>", lambda e: actions["search"]())
        self.entry.bind("<<ComboboxSelected>>", lambda e: actions["search"]())
        self.entry.bind("<FocusIn>",
                        lambda e: self.entry.configure(values=self.history.list()))

    # ---------- 视图状态刷新（行为方法） ----------
    def refresh_capture(self, running: bool, status_text: str):
        """根据取词服务状态刷新按钮、状态标签与状态灯。"""
        if running:
            self.capture_btn.config(
                text="停止取词模式",
                bg=COLORS["danger_bg"], fg=COLORS["danger_text"])
            self.status_label.config(text=f"取词模式: {status_text}",
                                     fg=COLORS["success_text"])
            self.set_led(True)
        else:
            self.capture_btn.config(
                text="启动取词模式",
                bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"])
            self.status_label.config(text=f"取词模式: {status_text}",
                                     fg=COLORS["text_disabled"])
            self.set_led(False)

    def set_led(self, on: bool):
        """更新取词状态灯颜色。"""
        color = COLORS["success_led"] if on else COLORS["text_disabled"]
        self.capture_led.itemconfig(self._led_item, fill=color)

    def set_topmost_mode(self, on: bool):
        """更新置顶按钮的文案与高亮态。"""
        if on:
            self.window_btn.config(
                text="取消置顶",
                bg=COLORS["primary"], fg=COLORS["primary_text_on"])
        else:
            self.window_btn.config(
                text="置顶显示",
                bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"])

    def set_hide_state(self, hidden: bool):
        """更新隐藏/显示按钮文案。"""
        if hidden:
            self.hide_btn.config(
                text="显示窗口", bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"])
        else:
            self.hide_btn.config(
                text="隐藏窗口", bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"])

    def focus_input(self):
        """初始焦点落到搜索输入框（P3-5）。"""
        self.entry.focus_set()