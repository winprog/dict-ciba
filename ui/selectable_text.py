"""只读可选中文本控件（Text 封装）。

原生 Label 不支持鼠标划选，无法复制结果文本。本控件用 Text 承载文本：
- state=normal 仅为保留「鼠标划选」能力，同时用 <Key>→break 禁用键盘编辑
- 支持划选高亮、Ctrl+C、右键菜单（复制 / 全选）
- exportselection=False：划选**不导出 X PRIMARY**，避免本应用结果区内的
  划选被全局取词服务（word_capture_service 轮询 PRIMARY）误判为「划词查询」；
  复制走 CLIPBOARD，与 PRIMARY 导出无关，故复制能力不受影响
- wrap="word" 随父容器宽度自动换行，高度按换行数贴合内容
- 背景可选；未指定时跟随父容器，视觉无缝
"""
import tkinter as tk


class SelectableText(tk.Text):
    """只读、可鼠标划选复制的 Text。"""

    def __init__(self, master, text, *, font, fg, bg=None, pad=6):
        if bg is None:
            try:
                bg = master.cget("background")
            except (tk.TclError, AttributeError):
                bg = "white"
        super().__init__(
            master, font=font, fg=fg, bg=bg, bd=0, highlightthickness=0,
            relief="flat", wrap="word", padx=pad, pady=pad,
            exportselection=False, takefocus=0, height=1, width=10,
            spacing1=0, spacing2=0, spacing3=0,
        )
        self.insert("1.0", text)
        # 只读但可选中：经 <Key> 过滤禁掉一切改写（粘贴/剪切/编辑），
        # 仅放行复制/全选走 Text 内建，鼠标划选与右键菜单不受影响
        self.bind("<Key>", _block_key, add="+")
        self.bind("<Button-3>", self._menu, add="+")
        self._fit_pending = None
        self._last_h = None
        # 构造时控件尚未映射、父宽度未定，不可急着算高度；
        # 交由映射后的 <Configure> 与自检回调在真实布局稳定时贴合。
        self._schedule(25)
        self.bind("<Configure>", self._on_resize, add="+")

    # ---------- 换行与高度贴合（映射后按真实显示宽度收敛） ----------
    def _schedule(self, ms):
        try:
            if self._fit_pending:
                self.after_cancel(self._fit_pending)
        except tk.TclError:
            pass
        self._fit_pending = self.after(ms, self._refit)

    def _on_resize(self, _event):
        # 父容器把实际显示宽度（fill 拉伸）定下来后才在此贴合
        self._refit()
        self._schedule(40)  # 布局尚未最终稳定时兜底再自检一次

    def _refit(self, _event=None):
        try:
            # 用控件自身的实际显示宽度（父容器 fill 决定），不手动改 width 选项
            avail = self.winfo_width()
        except tk.TclError:
            return
        if avail <= 1:                    # 尚未映射，晚点再试
            self._schedule(30)
            return
        try:
            self.update_idletasks()
            self.tk.call(self._w, "count", "-update", "1.0", "end-1c")
            n = int(self.tk.call(self._w, "count", "-displaylines", "1.0", "end-1c"))
            self.configure(height=max(1, n))
        except tk.TclError:
            return
        self._fit_pending = None
        if n != self._last_h:
            self._last_h = n
            self._schedule(25)            # 布局在收敛，再自检一次直到稳定

    # ---------- 右键菜单 ----------
    def _menu(self, _event=None):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="复制", command=lambda: self.event_generate("<<Copy>>"))
        menu.add_command(label="全选", command=lambda: self.tag_add("sel", "1.0", "end-1c"))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()


def _block_key(event):
    # 保证只读：仅放行不改变文本的组合键，其余一律拦截
    if event.state & 0x0004:                      # Ctrl 组合
        # 复制 / 全选安全，放行走内建；粘贴 / 剪切 / 其它组合一律拦截
        if event.keysym in ("c", "C", "a", "A"):
            return None
        return "break"
    # 无修饰键：只放行光标移动与修饰键；其余（含字符、回车、退格、删除）拦截
    if event.keysym in ("Right", "Left", "Up", "Down", "Home", "End",
                        "Shift_L", "Shift_R", "Control_L", "Control_R"):
        return None
    return "break"