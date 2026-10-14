"""ScrollArea 滚动区高度/边界回归测试。

锁定「滚到底出现白块」「滚不到底部新内容（如追问输入框）」两类回归：
_refresh 必须在 on_resize 回调（可能改变子控件折行高度）之后重新采集
bbox，使 scrollregion 底部不小于实际内容底部。
"""
import tkinter as tk

import pytest

from scroll_area import ScrollArea, _SCROLLBAR_W


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    yield root
    root.destroy()


def make_area(root, on_resize=None):
    area = ScrollArea(root, on_resize=on_resize)
    area.pack(fill="both", expand=True)
    root.update_idletasks()
    return area


def scroll_bottom(area):
    return _scroll_height(area.canvas)


def _scroll_height(canvas):
    return canvas.cget("scrollregion").split()[3] if canvas.cget("scrollregion") else 0


def test_scrollregion_reaches_bottom_after_frame_resize_check(tk_root):
    """滚动区底部内容（如追问输入框）必须被 scrollregion 覆盖。"""
    area = make_area(tk_root)
    # 模拟 LLM 对话：标题 + 气泡 + 底部输入行 Frame
    tk.Label(area.frame, text="AI 对话").pack(anchor="w")
    body = tk.Label(area.frame, text="这是较长的回复内容" * 5,
                    wraplength=200, justify="left")
    body.pack(anchor="w", fill="x")
    tk.Frame(area.frame, height=40).pack(fill="x", pady=10)  # 追问输入行

    # 用最小宽度触发 _refresh 路径
    area._refresh(area.canvas.winfo_width())

    region = area.canvas.cget("scrollregion")
    assert region
    _, _, _, bottom = (float(x) for x in region.split())
    frame_bottom = area.frame.winfo_reqheight()
    # scrollregion 底部不得小于内容底部（否则滚不到最底、出现白块）
    assert bottom >= frame_bottom


def test_scrollregion_grows_when_content_added_after_resize(tk_root):
    """on_resize 回调改变子控件高度后再次刷新，scrollregion 仍覆盖新底。"""
    calls = []

    def on_resize(w):
        calls.append(w)

    area = make_area(tk_root, on_resize=on_resize)

    def bottom():
        return float(_scroll_height(area.canvas)) if area.canvas.cget("scrollregion") else 0.0

    tk.Label(area.frame, text="先一条").pack(anchor="w")
    area._refresh(area.canvas.winfo_width())
    first = bottom()

    # 追加更长的底部内容（模拟追问后输入行，高度变化）
    tk.Label(
        area.frame,
        text=("追加的长内容。") * 40,
        wraplength=area.frame.winfo_width() - 20,
        justify="left",
    ).pack(anchor="w", fill="x")
    area._refresh(area.canvas.winfo_width())
    second = bottom()

    assert second > first
    assert second >= area.frame.winfo_reqheight()