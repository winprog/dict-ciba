import json
import re
import subprocess
import sys
import os
import time
import threading
from typing import Optional, Dict, Any
from tkinter import *
from tkinter import messagebox
from services.logger import get_logger, setup as setup_logging

logger = get_logger(__name__)

# LLM 对话总结导出目录（当前项目下本地工作目录，已被 .gitignore 排除、不提交仓库）
LLM_SUMMARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")

# 导入取词服务
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.capture_controller import CaptureController
from services.search_controller import SearchController
from services.word_state_manager import WordStateManager
from services.llm_conversation import LLMConversation
from ui.result_renderer import ResultRenderer
from services.llm_client import chat_messages as llm_chat_messages
from services.summary_exporter import request_summary
from services.desktop_placement import WindowPlacementService
from services.window_manager import WindowManager
from ui.llm_chat_view import LLMChatView
from ui.scroll_area import ScrollArea
from ui.ui_builder import MainView
from ui.ui_constants import COLORS, FONTS, PAD
from ui.spinner import make_spinner


# 窗口管理器（WM）舍入容差：geometry 设置的尺寸与 Configure/winfo 报告值
# 存在 ±1~4px 偏差，相等判定需容忍该误差
WINDOW_SIZE_TOLERANCE = 4

# 自动贴合时窗口至少能显示的正文字理行数：内容再短，窗口高度也不低于
# 「最小行数 × 行高」与初始默认高度的较大值，保证正常查词有足够阅读空间
MIN_WINDOW_LINES = 10


def _fit_min_window_height(initial_h, lines, extra, line_h=20):
    """自动贴合时窗口高度的底线：至少能显示 lines 行正文。

    initial_h: 初始默认窗口高度
    lines:     最少显示行数（MIN_WINDOW_LINES）
    extra:     窗口上下非内容区（标题/输入栏等）高度
    line_h:    单行正文估算高度（像素，兜底 20）
    """
    return max(initial_h, lines * line_h + extra)


def _should_shrink_window(cur_h, target_h, auto_fit_h, tolerance=WINDOW_SIZE_TOLERANCE):
    """判断是否应把窗口高度缩回内容所需高度。

    cur_h:      当前窗口实际高度
    target_h:   内容所需窗口高度（已封顶屏高 90%）
    auto_fit_h: 上次自动贴合设置的高度（None 表示从未自动贴合）
    tolerance:  窗口管理器报告高度与目标值之间的零点几像素舍入容差
    """
    if auto_fit_h is None:
        return False            # 窗口从未被程序撑大，不主动缩小
    if abs(cur_h - auto_fit_h) > tolerance:
        return False            # 用户手动改过窗口尺寸，尊重不缩
    return target_h < cur_h     # 内容变矮了才缩


def _resize_is_programmatic(w, h, cur_w, cur_h, pending=None, tolerance=WINDOW_SIZE_TOLERANCE):
    """判定 <Configure> 报告的 (w, h) 是否由程序自身生成，而非用户拖拽。

    程序自身操作会触发的几何变化有三类，其最终报告尺寸必然落入以下两
    个集合之一：
    1. pending —— 程序最近一次 place_window 请求的 (宽, 高)，覆盖
       show_window 重放置与 _apply_window_height 自动增高/缩回；
    2. cur_w/cur_h —— 程序记录的上一次生效尺寸，覆盖初始显示（映射时
       Configure 报告初始 geometry）与"同尺寸重放置"。

    因此只有两者都不吻合的尺寸变化才判定为用户手动接管，这样初始显示
    与每次取词后的重放置都不会被误判为"用户改过窗口"而打断自动贴合。
    """
    if pending is not None and abs(w - pending[0]) <= tolerance and abs(h - pending[1]) <= tolerance:
        return True
    if abs(w - cur_w) <= tolerance and abs(h - cur_h) <= tolerance:
        return True
    return False


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
        # 窗口初始默认尺寸（自动贴合缩回的底线）
        self.initial_window_width = window_width
        self.initial_window_height = window_height
        # 上次自动贴合设置的高度（None 表示窗口未被程序撑大/用户已手动接管）
        self.auto_fit_height = None
        # 程序最近一次 place_window 请求的 (宽, 高)，用于把 <Configure> 与用户拖拽区分开
        self._pending_program_geometry = None
        # 用户手动调整过窗口尺寸后置 True：自动增高/缩回完全停止，尊重用户设置
        self._user_lock_resize = False

        # 桌面定位服务（Facade）：解析桌面布局并计算窗口几何
        self._placement_service = WindowPlacementService()
        self.window_mgr = WindowManager(self.root, self._placement_service)

        # 单词状态管理器
        self.word_state_manager = WordStateManager()

        # LLM 多轮对话控制器
        self.conv = LLMConversation(
            system_prompt=(
                "你是一个中英文语言理解助手，能解释单词、短语、句子和段落，"
                "并支持多轮追问和深入解释。\n"
                "回答请始终使用简体中文；仅专有名词、代码、数学公式可保留原文/原样。\n"
                "原文若夹杂非常用分隔/装饰字符（如 ♣、✦、❀ 等花纹类符号），请一律忽略、"
                "仅视作分段，必须完整翻译或作答全文，不得从中途截断省略。"
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

        # 顶栏/输入面板装配（MainView 收口控件创建与状态刷新）
        self.view = MainView(self.root)
        self.view.bind_actions({
            "toggle_capture": self.toggle_capture_mode,
            "toggle_hover": self.toggle_hover_capture,
            "toggle_topmost": self.toggle_window_topmost,
            "hide": self.hide_window,
            "search": self.search,
            "search_llm": self.search_llm,
        })
        # 只保留业务频繁读写/高频访问的引用；按钮状态一律经 self.view 行为方法
        self.history = self.view.history
        self.entry = self.view.entry

        # 结果区域（滚动容器；业务渲染依赖 renderer 的回调链，保留在本类组装）
        self.result_frame = Frame(root, padx=PAD["result_h"], pady=PAD["result_v"])
        self.result_frame.pack(fill=BOTH, expand=True)

        # 可滚动结果区（收口 canvas/scrollbar/滚轮/布局刷新）
        self.scroll_area = ScrollArea(
            self.result_frame,
            on_resize=lambda w: self.renderer.update_wraplength(w),
        )
        self.scroll_area.pack(fill=BOTH, expand=True)
        self.scrollable_frame = self.scroll_area.frame  # 兼容引用
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
            on_export_summary=self._export_summary,
        )

        # 取词模式控制（服务生命周期与状态）
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
        self.view.focus_input()

    def toggle_hover_capture(self):
        """切换鼠标悬停取词设置"""
        self.capture.hover_enabled = self.view.enable_hover_var.get()
        if self.capture.running:
            # 取词模式正在运行，重启服务以应用新设置
            self.capture.apply_hover()
            self._render_capture_state()

    def toggle_capture_mode(self):
        """切换取词模式"""
        self.capture.hover_enabled = self.view.enable_hover_var.get()
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
        """根据 controller 状态刷新取词相关 UI（委托给 MainView）。"""
        self.capture_mode = self.capture.running
        self.view.refresh_capture(self.capture.running, self.capture.status_text)

    def toggle_window_topmost(self):
        """切换窗口置顶状态"""
        current_state = self.root.attributes('-topmost')
        new_state = not current_state
        self.root.attributes('-topmost', new_state)
        # 用户主动操作置顶，后续取词的临时置顶不再自动恢复
        self._user_manually_pinned = True
        self.view.set_topmost_mode(new_state)

    def hide_window(self):
        """隐藏窗口"""
        self.root.withdraw()  # 隐藏窗口
        self.window_visible = False
        self.view.set_hide_state(True)

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
        # 记录本次程序请求的尺寸：接下来 <Configure> 同尺寸事件不可误判为用户接管
        self._pending_program_geometry = (self.current_window_width, self.current_window_height)
        self.window_mgr.place_window(
            self.last_mouse_position,
            self.current_window_width,
            self.current_window_height,
        )
        self.window_visible = True
        self.view.set_hide_state(False)

    def on_focus_in(self, event=None):
        """窗口获得焦点时的处理"""
        # 取消自动隐藏定时器
        if self.auto_hide_timer:
            self.root.after_cancel(self.auto_hide_timer)
            self.auto_hide_timer = None

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
        notification = Label(self.view.top, text=f"已捕获: {word}",
                           font=FONTS["caption"], fg=COLORS["primary"],
                           bg=COLORS["card"])
        notification.pack(side=RIGHT, padx=PAD["pad_md"])

        # 3秒后自动移除通知
        self.root.after(3000, notification.destroy)

    # P3-2/P3-6：加载 spinner 由独立组件 spinner.make_spinner 提供

    def search(self):
        word = self.entry.get().strip()
        if not word:
            return

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        _, stop_spinner = make_spinner(self.scrollable_frame, f"正在查词: {word}")
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
        # 普通查词渲染后同样自动贴合窗口（可增可缩，尊重用户手动调整）
        self.root.after(120, self._fit_window_for_content)

    def _search_error(self, error):
        """P3-3：搜索错误内联为红色条带，不再弹 messagebox。"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        bar = Frame(self.scrollable_frame, bg=COLORS["danger_bg"])
        bar.pack(fill=X, pady=PAD["pad_md"])
        Label(bar, text=f"⚠️ 查询失败：{error}", font=FONTS["label"],
              fg=COLORS["danger_text"], bg=COLORS["danger_bg"]).pack(anchor=W, padx=PAD["pad_md"], pady=PAD["pad_s"])

        self.root.after(50, self.scroll_area.force_layout)
        self.root.after(120, self._fit_window_for_content)

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
        self._llm_scroll_to_input()

    def _llm_scroll_to_input(self):
        """把结果区滚到最底，让最新消息气泡（或加载态）与追问输入框立即可见。"""
        self.root.after(0, lambda: self.scroll_area.canvas.yview_moveto(1.0))

    def _llm_scroll_to_latest_answer(self):
        """回答到达后，把视口定位到最新一轮「问题」的起始处，让追问与回答开头一起显示。"""
        v = self.llm_view
        anchor = v.latest_question_widget or v.latest_answer_widget
        self.root.after(0, lambda: self.scroll_area.scroll_to_widget(anchor))

    def _fit_window_for_content(self, scroll_to=None):
        """查询/回答渲染后按内容实际高度自动贴合窗口（可增可缩）。

        普通查词与 LLM 回答渲染后都会调用：
        - 内容变长自动增高；内容变矮且窗口仍停留在上次自动贴合的高度
          （即用户未手动调整过）时缩回内容所需高度；
        - 缩回底线为「最少显示行数 MIN_WINDOW_LINES × 行高 + 非内容区」
          与初始默认高度的较大值，避免 LLM 短回答把窗口缩得过小、正常
          查词时显示不完整；
        - 上限为屏幕高度的 90%，内容再长仍由 ScrollArea 滚动兜底；
        - 用户手动调整过窗口尺寸后（_user_lock_resize）完全停止贴合。

        scroll_to: 非 None 时，增高/缩回后把视口定位到该控件顶部
                   （LLM 回答传入最新一轮问题气泡；普通查词传 None 不滚动）。
        """
        if self._user_lock_resize:
            return
        # 无内容（如查询失败前/初始态）不贴合；llm 视图控件也被 scrollable_frame 统一承载
        if not self.scrollable_frame.winfo_children():
            return
        try:
            self.scroll_area.frame.update_idletasks()
            bbox = self.scroll_area.canvas.bbox("all")
            content_h = bbox[3] - bbox[1] if bbox else 0
            screen_h = self.root.winfo_screenheight()
            if screen_h <= 0 or content_h <= 0:
                return
            # 需要的最小窗口高度 = 内容高度 + 窗口上下非内容区（标题/输入等）
            extra = max(0, self.root.winfo_height() - self.scroll_area.canvas.winfo_height())
            target_h = min(int(screen_h * 0.9), content_h + extra + 20)
            # 最底线：至少能显示 MIN_WINDOW_LINES 行正文（行高按正文实际字体估算）
            target_h = max(target_h, self._fit_min_window_height_extra(extra))
            cur_h = self.root.winfo_height()
            if target_h <= cur_h:
                # 内容未撑破当前窗口：仅当窗口正处于自动贴合高度（用户没手动改过）且内容明显变矮时缩回
                if not _should_shrink_window(cur_h, target_h, self.auto_fit_height):
                    return
                if target_h >= cur_h:
                    return
            # 内容变长自动增高 / 内容变矮自动缩回：均记录本次贴合高度供后续判定
            self.auto_fit_height = target_h
            self._apply_window_height(target_h, scroll_to=scroll_to)
        except Exception:
            return

    def _fit_min_window_height_extra(self, extra):
        """当前正文行高估算下的窗口最底线高度。"""
        line_h = 20
        try:
            from tkinter import font as tkfont
            line_h = tkfont.Font(font=FONTS["body"]).metrics("linespace") or 20
        except Exception:
            pass
        return _fit_min_window_height(self.initial_window_height, MIN_WINDOW_LINES, extra, line_h)

    def _apply_window_height(self, target_h, scroll_to=None):
        """以 target_h 重新放置窗口，并按需滚动视口。

        scroll_to 非 None 时对齐到该控件顶部（LLM 回答场景把视口定位到
        最新一轮问题的起始处）；普通查词传 None，保持视口在内容顶部。
        """
        self.current_window_height = target_h
        # 记录本次程序请求的宽度/高度：随后触发的 <Configure> 与之相符即视为程序贴合
        self._pending_program_geometry = (self.current_window_width, target_h)
        self.window_mgr.place_window(
            self.last_mouse_position,
            self.current_window_width,
            self.current_window_height,
        )
        if scroll_to is not None:
            self.root.after(0, lambda: self.scroll_area.scroll_to_widget(scroll_to))

    def _ask_llm(self):
        """提交追问"""
        if not self.llm_view.llm_input:
            return
        question = self.llm_view.llm_input.get().strip()
        if not self.conv.ask(question):
            return  # 输入为空或上一轮仍在加载
        self.llm_view.render(self.conv.history, loading=True)
        self._llm_scroll_to_input()

    def _export_summary(self):
        """对历史问答做总结并导出到本地 exports 目录（不离场/不入仓）。

        后台线程调用 LLM，完成后回主线程把总结追加进对话并提示保存路径。
        """
        if not self.conv.history:
            messagebox.showinfo("导出对话总结", "暂无对话可总结。")
            return
        btn = self.llm_view.summary_btn
        if btn:
            btn.config(state=DISABLED, text="总结中…")
        history = list(self.conv.history)

        def worker():
            try:
                summary, path = request_summary(history, llm_chat_messages, LLM_SUMMARY_DIR)
            except Exception as ex:
                self.root.after(0, lambda e=ex: self._export_summary_done(None, None, e))
                return
            self.root.after(0, lambda s=summary, p=path: self._export_summary_done(s, p, None))

        threading.Thread(target=worker, daemon=True).start()

    def _export_summary_done(self, summary, path, error):
        """总结线程的回主线程落地：恢复按钮、把结果或错误追加进对话。"""
        btn = self.llm_view.summary_btn
        if btn:
            btn.config(state=NORMAL, text="导出对话总结")
        if error is not None:
            self.conv.append_assistant(f"⚠️ 对话总结导出失败：{error}")
        else:
            self.conv.append_assistant(f"📄 对话总结（已导出：{path}）\n\n{summary}")
        self.llm_view.render(self.conv.history, loading=False)
        if path:
            self._llm_scroll_to_latest_answer()

    def _llm_commit(self, ans):
        """主线程接收 LLM 回答：写入历史并渲染"""
        self.conv.append_assistant(ans)
        if isinstance(self.current_data, dict):
            self.current_data["translation"] = ans
        self.llm_view.render(self.conv.history, loading=False)
        self._llm_scroll_to_latest_answer()
        # LLM 回答渲染后自动贴合窗口；视口定位到最新一轮问题起始处
        self._fit_window_for_content(
            self.llm_view.latest_question_widget or self.llm_view.latest_answer_widget)

    def _llm_error(self, error):
        self.conv.append_assistant(f"⚠️ {error}")
        self.llm_view.render(self.conv.history, loading=False)
        self._llm_scroll_to_latest_answer()

    def display_result(self, data):
        """渲染词典/LLM 查询结果（委托给 ResultRenderer）"""
        self.renderer.render(data)

    def _on_window_resize(self, event):
        """窗口尺寸变化时记录新尺寸，并区分自动贴合与用户手动接管。

        - 程序自身重放置（初始显示、show_window 重放置、_apply_window_height
          自动增高/缩回）触发的 <Configure>：尺寸与程序请求/记录一致，仅同步
          实际尺寸、并把 auto_fit_height 校准为 WM 实际报告值，不打断贴合；
        - 与程序记录尺寸不一致的变化视为用户手动接管：记录实际尺寸、解除
          自动贴合（auto_fit_height=None）并钉住 _user_lock_resize，此后
          自动增高/缩回全部停止，完全尊重用户设置的窗口大小（这正是"长结果
          撑大窗口后短结果不回缩"修复的关键）。
        """
        if not (event and hasattr(event, 'width') and hasattr(event, 'height')):
            return
        w, h = event.width, event.height
        if w <= 0 or h <= 0:
            return
        if _resize_is_programmatic(
                w, h,
                self.current_window_width, self.current_window_height,
                self._pending_program_geometry):
            # 程序自身操作的几何变化：仅同步，并吸收 pending（若已落定）
            if self._pending_program_geometry is not None:
                self._pending_program_geometry = None
            self.current_window_width = w
            self.current_window_height = h
            if self.auto_fit_height is not None:
                # 以 WM 实际报告值校准，缩回判定更稳（geometry 与报告存在 ±1~4px 偏差）
                self.auto_fit_height = h
            return
        # 用户手动调整窗口尺寸：记录实际尺寸并永久解除自动贴合
        self.current_window_width = w
        self.current_window_height = h
        self.auto_fit_height = None
        self._user_lock_resize = True

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