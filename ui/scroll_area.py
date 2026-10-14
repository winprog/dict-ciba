"""可滚动结果区控件（P2 拆分）。

把 Canvas + 滚动条 + 内容 Frame + 滚轮事件 + 布局换行刷新收口为一个
自管理控件，替代 DictionaryApp 内手写的 canvas 结构，消除
_force_canvas_resize / _on_canvas_resize / 滚轮处理三处散落逻辑。
"""

from tkinter import *

try:
    from services.logger import get_logger
except Exception:  # 独立运行兜底
    import logging
    get_logger = logging.getLogger

_SCROLLBAR_W = 20          # 滚动条占宽
_MIN_FRAME_W = 400         # 内容最小宽度


class ScrollArea(Frame):
    """自管理的垂直滚动容器。

    属性 .frame 为内容区 Frame（调用方把渲染内容放里面）；
    布局刷新时会回调 on_resize(frame_width)，供调用方同步换行宽度。

    需要随全局滚轮时调用 bind_mousewheel(root)。
    """

    def __init__(self, master, on_resize=None, **kw):
        super().__init__(master, **kw)
        self._on_resize = on_resize
        self._log = get_logger(__name__)

        self.canvas = Canvas(self)
        self.scrollbar = Scrollbar(self, orient=VERTICAL, command=self.canvas.yview)
        self.frame = Frame(self.canvas)

        self.frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self._window_id = self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", self._fit_content)
        self.canvas.focus_set()

        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)

    def bind_mousewheel(self, root):
        """把滚轮事件统一绑定到 root，保证结果区/输入框/滚动条滚动一致。"""
        root.bind_all("<MouseWheel>", self._on_mousewheel)
        root.bind_all("<Button-4>", self._on_linux_mousewheel)
        root.bind_all("<Button-5>", self._on_linux_mousewheel)

    def force_layout(self):
        """内容变化后强制重排（先让新内容完成布局再刷新宽度）。"""
        self.frame.update_idletasks()
        self._refresh(self.canvas.winfo_width())

    def _fit_content(self, event=None):
        """Canvas 尺寸变化时，让内容 Frame 撑满并重算换行。"""
        self._refresh(self.canvas.winfo_width())

    def _refresh(self, canvas_width):
        if not self._window_id or canvas_width <= 0:
            return
        frame_width = max(_MIN_FRAME_W, canvas_width - _SCROLLBAR_W)

        self.frame.config(width=frame_width)
        self.canvas.itemconfigure(self._window_id, width=frame_width)
        # 先让内容完成当前宽度下的布局
        self.frame.update_idletasks()

        if self._on_resize:
            self._on_resize(frame_width)

        # 回调可能改变子控件折行/高度，需再布局后再采集边界，
        # 否则 scrollregion 偏小，滚到底出现白块、滚不到底部内容（如追问输入框）。
        self.frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """标准滚轮（Windows/mac）：delta>0 上滚。"""
        delta = -1 * (event.delta // 120)
        self.canvas.yview_scroll(delta, "units")
        self._log.debug(f"滚轮: delta={event.delta}")
        return "break"

    def _on_linux_mousewheel(self, event):
        """Linux Button-4/5 滚轮。"""
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        return "break"