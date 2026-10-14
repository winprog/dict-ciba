import json
import re
import html
import subprocess
import sys
import os
import time
from typing import Optional, Dict, Any
from tkinter import *
from tkinter import ttk, messagebox
from logger import get_logger, setup as setup_logging

logger = get_logger(__name__)

# 导入取词服务
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from capture_controller import CaptureController
from search_controller import SearchController
from word_state_manager import WordStateManager
from llm_conversation import LLMConversation
from search_history import SearchHistory
from result_renderer import ResultRenderer
from llm_client import chat_messages as llm_chat_messages
import markdown
from tkinterweb import HtmlFrame
from desktop_placement import WindowPlacementService
from window_manager import WindowManager
from llm_chat_view import LLMChatView
from scroll_area import ScrollArea
from ui_constants import COLORS, FONTS, SPACING, PAD


class DictionaryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dictionary")

        # 获取屏幕尺寸
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        # 根据屏幕分辨率计算窗口尺寸
        # 对于高分辨率屏幕(3840x2160)，使用更大的窗口
        if screen_width >= 3840 and screen_height >= 2160:
            # 4K屏幕使用大窗口
            window_width = 820
            window_height = 600
        elif screen_width >= 2560:
            # 2K屏幕使用中等窗口
            window_width = 650
            window_height = 500
        else:
            # 普通屏幕使用默认尺寸
            window_width = 500
            window_height = 400
        x = screen_width - window_width - 50  # 距离右边50像素
        y = screen_height - window_height - 50  # 距离底部50像素

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 窗口管理状态
        self.capture_mode = False
        self.window_visible = True
        self.auto_hide_timer = None
        self.original_geometry = None
        self.last_mouse_position = None  # 记录最后一次取词位置
        # 用户是否手动点过置顶按钮（若是，取词后的临时置顶不做自动恢复）
        self._user_manually_pinned = False

        # 记录当前窗口尺寸，用于记忆用户调整的大小
        # 初始化为默认尺寸
        self.current_window_width = window_width
        self.current_window_height = window_height

        # 桌面定位服务（Facade）：解析桌面布局并计算窗口几何
        self._placement_service = WindowPlacementService()
        self.window_mgr = WindowManager(self.root, self._placement_service)

        # 单词状态管理器
        self.word_state_manager = WordStateManager()

        # LLM 多轮对话控制器
        self._llm_input = None  # 追问输入框（由 LLMChatView 维护，保留字段兼容）
        self.conv = LLMConversation(
            system_prompt=(
                "你是一个中英文语言理解助手，能解释单词、短语、句子和段落，"
                "并支持多轮追问和深入解释。"
            ),
            chat=llm_chat_messages,
            on_answer=lambda ans: self.root.after(
                0, lambda a=ans: self._llm_commit(a)
            ),
            on_error=lambda err: self.root.after(
                0, lambda e=err: self._llm_error(e)
            ),
        )

        # 设置窗口初始属性
        self.root.attributes('-topmost', False)  # 初始不在最上层
        self.root.attributes('-alpha', 0.95)     # 设置透明度

        # 绑定窗口焦点事件
        self.root.bind('<FocusIn>', self.on_focus_in)

        # 顶部按钮区域
        self.top_frame = Frame(root, pady=PAD["pad_s"])
        self.top_frame.pack(fill=X)

        # 取词模式状态灯（绿点亮 = 取词运行中）
        self.capture_led = Canvas(self.top_frame, width=12, height=12,
                                  highlightthickness=0, bg=self.root.cget("bg"))
        self._led_item = self.capture_led.create_oval(
            2, 2, 10, 10, fill=COLORS["text_disabled"], outline=""
        )
        self.capture_led.pack(side=LEFT, padx=(PAD["pad_md"], PAD["pad_xs"]))

        # 取词模式按钮
        self.capture_btn = Button(self.top_frame, text="启动取词模式",
                                 command=self.toggle_capture_mode,
                                 bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"],
                                 font=FONTS["caption"])
        self.capture_btn.pack(side=LEFT, padx=PAD["pad_md"])

        # 状态标签
        self.status_label = Label(self.top_frame, text="取词模式: 关闭",
                                 font=FONTS["caption"], fg=COLORS["text_secondary"])
        self.status_label.pack(side=LEFT, padx=PAD["pad_md"])

        # 鼠标悬停取词选项
        self.enable_hover_var = BooleanVar(value=False)  # 默认禁用鼠标悬停
        self.hover_check = Checkbutton(self.top_frame, text="启用鼠标悬停取词",
                                       variable=self.enable_hover_var,
                                       font=FONTS["caption"],
                                       command=self.toggle_hover_capture)
        self.hover_check.pack(side=LEFT, padx=PAD["pad_md"])

        # 窗口控制按钮
        self.window_btn = Button(self.top_frame, text="置顶显示",
                                command=self.toggle_window_topmost,
                                bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"],
                                font=FONTS["caption"])
        self.window_btn.pack(side=RIGHT, padx=PAD["pad_s"])

        self.hide_btn = Button(self.top_frame, text="隐藏窗口",
                               command=self.hide_window,
                               bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"],
                               font=FONTS["caption"])
        self.hide_btn.pack(side=RIGHT, padx=PAD["pad_s"])

        # 输入区域
        self.input_frame = Frame(root, pady=PAD["pad_md"])
        self.input_frame.pack(fill=X)

        # P3-4 搜索历史（Combobox + 最近 20 条，JSON 持久化）
        self.history = SearchHistory()
        self.entry = ttk.Combobox(self.input_frame, font=FONTS["input"],
                                  values=self.history.list())
        self.entry.pack(side=LEFT, fill=X, expand=True, padx=(PAD["pad_md"], PAD["pad_s"]))
        self.entry.bind("<Return>", lambda e: self.search())
        self.entry.bind("<<ComboboxSelected>>", lambda e: self.search())
        self.entry.bind("<FocusIn>", lambda e: self.entry.configure(values=self.history.list()))

        self.btn = Button(self.input_frame, text="Search", command=self.search,
                          bg=COLORS["primary"], fg=COLORS["primary_text_on"],
                          font=FONTS["small"], relief=FLAT)
        self.btn.pack(side=RIGHT, padx=(PAD["pad_s"], 0))

        self.llm_btn = Button(self.input_frame, text="LLM", command=self.search_llm,
                              bg=COLORS["primary"], fg=COLORS["primary_text_on"],
                              font=FONTS["small"], relief=FLAT)
        self.llm_btn.pack(side=RIGHT, padx=(0, PAD["pad_md"]))

        # 结果区域
        self.result_frame = Frame(root, padx=PAD["result_h"], pady=PAD["result_v"])
        self.result_frame.pack(fill=BOTH, expand=True)

        # 可滚动结果区（收口 canvas/scrollbar/滚轮/布局刷新）
        self.scroll_area = ScrollArea(
            self.result_frame,
            on_resize=lambda w: self.renderer.update_wraplength(w),
        )
        self.scrollable_frame = self.scroll_area.frame  # 兼容引用
        self.canvas_window_id = None  # 兼容旧判断，无需再置
        self.scroll_area.bind_mousewheel(self.root)

        # 绑定窗口大小变化事件，记录窗口尺寸
        self.root.bind("<Configure>", self._on_window_resize)

        self.current_data = None

        # 词典结果内容渲染器（P2-5）：把查询数据渲染进滚动区域
        self.renderer = ResultRenderer(
            self.scrollable_frame,
            get_frame_width=lambda: self.current_window_width,
        )

        # LLM 对话视图（纯渲染；业务由 self.conv + _ask_llm 承担）
        self.llm_view = LLMChatView(
            self.scrollable_frame,
            on_resize=lambda: self.scroll_area.force_layout(),
            on_submit=self._ask_llm,
        )

        # 取词模式控制（服务生命周期与状态）
        self.capture_mode = False  # 兼容旧字段，由 controller 同步
        self.capture = CaptureController(
            on_captured_word=self.handle_captured_word
        )
        # 搜索分流控制
        self.search_ctrl = SearchController()

        # 窗口关闭时停止取词服务
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # P3-1 应用内快捷键（窗口聚焦即生效；系统级全局热键依赖 Wayland 桌面注册）
        self._register_shortcuts()
        # P3-5 初始焦点落到输入框
        self.entry.focus_set()

    def toggle_hover_capture(self):
        """切换鼠标悬停取词设置"""
        self.capture.hover_enabled = self.enable_hover_var.get()
        if self.capture.running:
            # 取词模式正在运行，重启服务以应用新设置
            self.capture.apply_hover()
            self._render_capture_state()

    def toggle_capture_mode(self):
        """切换取词模式"""
        self.capture.hover_enabled = self.enable_hover_var.get()
        if not self.capture.running:
            # 启动取词模式
            try:
                self.capture.start()
                self._render_capture_state()
            except Exception as e:
                messagebox.showerror("错误", f"启动取词服务失败: {e}")
        else:
            # 停止取词模式
            self.capture.stop()
            self._render_capture_state()

    def _render_capture_state(self):
        """根据 controller 状态刷新取词相关 UI。"""
        self.capture_mode = self.capture.running
        status_text = f"取词模式: {self.capture.status_text}"
        if self.capture.running:
            self.capture_btn.config(
                text="停止取词模式",
                bg=COLORS["danger_bg"], fg=COLORS["danger_text"],
            )
            self.status_label.config(
                text=status_text, fg=COLORS["success_text"]
            )
            self._set_led(True)
        else:
            self.capture_btn.config(
                text="启动取词模式",
                bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"],
            )
            self.status_label.config(
                text=status_text, fg=COLORS["text_disabled"]
            )
            self._set_led(False)

    def _set_led(self, on: bool):
        """更新取词状态灯颜色"""
        color = COLORS["success_led"] if on else COLORS["text_disabled"]
        self.capture_led.itemconfig(self._led_item, fill=color)

    def toggle_window_topmost(self):
        """切换窗口置顶状态"""
        current_state = self.root.attributes('-topmost')
        new_state = not current_state
        self.root.attributes('-topmost', new_state)
        # 用户主动操作置顶，后续取词的临时置顶不再自动恢复
        self._user_manually_pinned = True

        if new_state:
            self.window_btn.config(
                text="取消置顶", bg=COLORS["primary"],
                fg=COLORS["primary_text_on"],
            )
        else:
            self.window_btn.config(
                text="置顶显示", bg=COLORS["neutral_bg"],
                fg=COLORS["text_secondary"],
            )

    def hide_window(self):
        """隐藏窗口"""
        self.root.withdraw()  # 隐藏窗口
        self.window_visible = False
        self.hide_btn.config(
            text="显示窗口", bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"]
        )

        # 取消之前的定时器
        if self.auto_hide_timer:
            self.root.after_cancel(self.auto_hide_timer)
            self.auto_hide_timer = None

    def _register_shortcuts(self):
        """P3-1 应用内快捷键：Esc 隐藏、Ctrl+Shift+C 开关取词。"""
        self.root.bind_all("<Escape>", lambda e: self.hide_window())
        self.root.bind_all("<Control-Shift-c>", lambda e: self.toggle_capture_mode())

    def show_window(self):
        """显示窗口（几何放置/DeskTop 切换委托给 WindowManager）"""
        self.window_mgr.place_window(
            self.last_mouse_position,
            self.current_window_width,
            self.current_window_height,
        )
        self.window_visible = True
        self.hide_btn.config(
            text="隐藏窗口", bg=COLORS["neutral_bg"], fg=COLORS["text_secondary"]
        )

    def on_focus_in(self, event=None):
        """窗口获得焦点时的处理"""
        # 取消自动隐藏定时器
        if self.auto_hide_timer:
            self.root.after_cancel(self.auto_hide_timer)
            self.auto_hide_timer = None

    def clean_punctuation(self, text):
        """清理文本前后的标点符号"""
        if not text:
            return text

        # 中英文标点符号
        punctuation_chars = '.,!?;:"\'`，。！？；："\'（）【】《》<>[]{}()'

        # 清理开头的标点符号
        while text and text[0] in punctuation_chars:
            text = text[1:]

        # 清理结尾的标点符号
        while text and text[-1] in punctuation_chars:
            text = text[:-1]

        return text.strip()

    def set_mouse_position(self, x, y):
        """记录鼠标取词位置"""
        self.last_mouse_position = (x, y)

    def handle_captured_word(self, word, mouse_x=None, mouse_y=None):
        """处理捕获到的单词"""
        # 使用状态管理器处理新单词
        result = self.word_state_manager.handle_new_word(word)

        # 调试信息
        logger.debug(f"DEBUG DictionaryApp: 处理结果={result}")

        if not result['should_process']:
            # 不需要处理的情况：空单词或相同单词
            logger.debug(f"DEBUG DictionaryApp: 跳过处理，原因: {result['reason']}")
            return

        # 记录鼠标位置（如果提供了）
        if mouse_x is not None and mouse_y is not None:
            self.set_mouse_position(mouse_x, mouse_y)

        # 在GUI线程中更新界面
        self.root.after(0, lambda: self._process_captured_word(result['cleaned_word']))

    def _process_captured_word(self, word):
        """在GUI线程中处理捕获的单词"""
        logger.info(f"🔍 [_process_captured_word] 开始处理捕获的单词: '{word}'")

        # 状态管理器已经处理了单词比较，这里直接处理新单词
        logger.debug(f"DEBUG DictionaryApp: 处理新单词 '{word}'")

        # 更新状态管理器中的当前单词
        self.word_state_manager.update_current_word(word)

        # 显示窗口（只根据取词状态决定）
        logger.debug("🔍 [_process_captured_word] 调用show_window()")
        self.show_window()

        # 临时置顶窗口以便查看结果（记录为"自动置顶"，可被自动恢复）
        self.root.attributes('-topmost', True)
        self._user_manually_pinned = False
        logger.debug("🔍 [_process_captured_word] 窗口已置顶")

        # 更新输入框（只有不同单词才更新）
        self.entry.delete(0, END)
        self.entry.insert(0, word)

        # 自动搜索
        logger.debug("🔍 [_process_captured_word] 开始自动搜索")
        self.search()

        # 显示捕获提示
        self.show_capture_notification(word)

        # 3秒后取消置顶（如果用户没有手动置顶）
        self.root.after(3000, self._restore_window_state)

        logger.info("🔍 [_process_captured_word] 单词处理完成")

    def _restore_window_state(self):
        """恢复窗口状态"""
        # 用户手动置顶过：尊重用户操作，不自动取消
        if self._user_manually_pinned:
            return
        # 仅当窗口处于置顶状态时才取消（取词触发的临时置顶）
        if self.root.attributes('-topmost'):
            self.root.attributes('-topmost', False)

    def show_capture_notification(self, word):
        """显示捕获成功的通知"""
        # 创建临时通知标签
        notification = Label(self.top_frame, text=f"已捕获: {word}",
                           font=FONTS["caption"], fg=COLORS["primary"],
                           bg=COLORS["card"])
        notification.pack(side=RIGHT, padx=PAD["pad_md"])

        # 3秒后自动移除通知
        self.root.after(3000, notification.destroy)

    # P3-2/P3-6：加载 spinner 帧 + 进度文案
    _SPINNER_FRAMES = ["|", "/", "-", "\\"]

    def _make_spinner(self, parent, text):
        """创建带 spinning 动画的进度标签。

        返回 (label, stop)。stop() 停止动画并销毁标签，幂等。
        """
        label = Label(parent, text=f"{self._SPINNER_FRAMES[0]} {text}",
                      font=FONTS["label"], fg=COLORS["text_secondary"])
        label.pack(anchor=W, pady=PAD["pad_md"])
        state = {"running": True}

        def _spin(idx):
            if not state["running"]:
                return
            label.config(text=f"{self._SPINNER_FRAMES[idx % 4]} {text}")
            state["timer"] = label.after(120, lambda: _spin(idx + 1))

        def _stop():
            state["running"] = False
            try:
                if state.get("timer"):
                    label.after_cancel(state["timer"])
            except Exception:
                pass
            try:
                label.destroy()
            except Exception:
                pass

        _spin(0)
        return label, _stop

    def search(self):
        word = self.entry.get().strip()
        if not word:
            return

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        _, stop_spinner = self._make_spinner(self.scrollable_frame, f"正在查词: {word}")
        self.root.update()

        def on_result(data):
            self.history.add(word)
            self.root.after(0, lambda: (stop_spinner(), self._display_result(data)))

        def on_llm(w):
            self.root.after(0, lambda: (stop_spinner(), self._switch_to_llm_chat(w)))

        def on_error(ex):
            self.root.after(0, lambda: (stop_spinner(), self._search_error(ex)))

        self.search_ctrl.get(word, on_result=on_result, on_llm=on_llm, on_error=on_error)

    def _display_result(self, data):
        """显示搜索结果"""
        self.current_data = data
        self.display_result(data)

        # 强制触发布局刷新，确保首次显示时正确填充
        self.root.after(50, self.scroll_area.force_layout)

    def _search_error(self, error):
        """P3-3：搜索错误内联为红色条带，不再弹 messagebox。"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        bar = Frame(self.scrollable_frame, bg=COLORS["danger_bg"])
        bar.pack(fill=X, pady=PAD["pad_md"])
        Label(bar, text=f"⚠️ 查询失败：{error}", font=FONTS["label"],
              fg=COLORS["danger_text"], bg=COLORS["danger_bg"]).pack(anchor=W, padx=PAD["pad_md"], pady=PAD["pad_s"])

        self.root.after(50, self.scroll_area.force_layout)

    def _switch_to_llm_chat(self, word):
        """从搜索流程切换到 LLM 多轮对话视图"""
        self._start_llm_chat(word)

    def search_llm(self):
        """普通翻译区点击 LLM：将输入框内容直接用 LLM 对话翻译"""
        word = self.entry.get().strip()
        if not word:
            return
        self._start_llm_chat(word)

    def _start_llm_chat(self, word):
        """以 word 为初始问题开启 LLM 对话"""
        self.current_data = {"result_type": "llm_translation", "word": word}
        self.conv.start(word)
        self.llm_view.render(self.conv.history, loading=True)

    def _ask_llm(self):
        """提交追问"""
        if not self.llm_view.llm_input:
            return
        question = self.llm_view.llm_input.get().strip()
        if not self.conv.ask(question):
            return  # 输入为空或上一轮仍在加载
        self.llm_view.render(self.conv.history, loading=True)

    def _llm_commit(self, ans):
        """主线程接收 LLM 回答：写入历史并渲染"""
        self.conv.append_assistant(ans)
        if isinstance(self.current_data, dict):
            self.current_data["translation"] = ans
        self.llm_view.render(self.conv.history, loading=False)

    def _llm_error(self, error):
        self.conv.append_assistant(f"⚠️ {error}")
        self.llm_view.render(self.conv.history, loading=False)

    def display_result(self, data):
        """渲染词典/LLM 查询结果（委托给 ResultRenderer）"""
        self.renderer.render(data)

    def _on_window_resize(self, event):
        """当窗口大小变化时，记录新的窗口尺寸"""
        if event and hasattr(event, 'width') and hasattr(event, 'height'):
            # 使用初始化时的窗口尺寸作为最小阈值，确保窗口不会小于初始化大小
            min_width = self.current_window_width
            min_height = self.current_window_height
            if event.width >= min_width and event.height >= min_height:
                # 只有当尺寸大于最小阈值时才更新
                self.current_window_width = event.width
                self.current_window_height = event.height

    def on_closing(self):
        """窗口关闭时的处理"""
        if self.capture.running:
            self.capture.stop()
        self.root.destroy()


if __name__ == "__main__":
    setup_logging()
    root = Tk()
    app = DictionaryApp(root)
    root.mainloop()