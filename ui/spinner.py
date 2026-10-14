"""加载 spinner 动画（独立渲染组件，供业务层在查询期间展示非阻塞进度）。"""
from tkinter import Label

from ui.ui_constants import COLORS, FONTS, PAD

_FLAG = ["|", "/", "-", "\\"]


def make_spinner(parent, text):
    """创建带 spinning 动画的进度标签。

    返回 (label, stop)。stop() 停止动画并销毁标签，幂等。
    """
    label = Label(parent, text=f"{_FLAG[0]} {text}",
                  font=FONTS["label"], fg=COLORS["text_secondary"])
    label.pack(anchor="w", pady=PAD["pad_md"])
    state = {"running": True}

    def _spin(idx):
        if not state["running"]:
            return
        label.config(text=f"{_FLAG[idx % 4]} {text}")
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