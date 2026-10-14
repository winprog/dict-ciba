"""LLMChatView.render 的渲染流程与回归测试。

气泡改用原生 Label + wraplength 渲染（取代 HtmlFrame），因此本测试断言：
气泡是 Label、文本正确（无 markdown 星号/无字面 <p>）、折行宽度>0，并在
容器 resize 时刷新 wraplength —— 锁定「行高挤压」「大片空白」「横向溢出」
等 HtmlFrame 布局回归。
"""
import tkinter as tk

import pytest

import llm_chat_view
from ui_constants import COLORS, FONTS


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    yield root
    root.destroy()


def make_view(root):
    frame = tk.Frame(root)
    frame.pack()
    return llm_chat_view.LLMChatView(frame, on_resize=lambda: None, on_submit=lambda: None)


def texts(w):
    out = []

    def walk(w):
        for ch in w.winfo_children():
            try:
                t = ch.cget("text")
            except tk.TclError:
                t = None
            if t:
                out.append(t)
            walk(ch)

    walk(w)
    return out


def bubble_labels(w):
    """返回对话气泡（带气泡背景色的 Label）。"""
    bubble_bg = (COLORS["bubble_ai"], COLORS["bubble_user"])
    out = []
    for ch in w.winfo_children():
        try:
            if ch.cget("background") in bubble_bg:
                out.append(ch)
        except tk.TclError:
            continue
    return out


def test_render_user_loading_shows_title_input_spinner(tk_root):
    v = make_view(tk_root)
    v.render([{"role": "user", "content": "hello"}], loading=True)
    labels = texts(v._frame)
    assert "AI 多轮对话（可继续追问）" in labels
    assert v.llm_input is not None
    assert "AI 思考中..." in labels


def test_render_user_and_assistant_bubbles(tk_root):
    """user 气泡保留原文本；assistant 降为纯文本且折行宽度>0。"""
    v = make_view(tk_root)
    v.render(
        [{"role": "user", "content": "a<b>c"}, {"role": "assistant", "content": "**bold** 第一段\n\n- 列表项"}],
        loading=False,
    )
    bubbles = bubble_labels(v._frame)
    assert len(bubbles) == 2
    # user 气泡原样展示（Label 不做 HTML 转义，也不应有字面 <p> 残留）
    assert bubbles[0].cget("text") == "a<b>c"
    # assistant 去除 ** 标记、保留内容
    asst_text = bubbles[1].cget("text")
    assert "**" not in asst_text
    assert "bold" in asst_text
    assert "•" in asst_text
    # 每个气泡都有正折行宽度（防止横向溢出回归）
    assert all(b.cget("wraplength") > 0 for b in bubbles)


def test_render_after_widgets_destroyed_rebuilds(tk_root):
    """模拟字典搜索 destroy 掉 scrollable_frame 子控件后，渲染 LLM 视图仍自愈。"""
    v = make_view(tk_root)
    for w in v._frame.winfo_children():
        w.destroy()
    v.render([{"role": "user", "content": "word"}], loading=False)
    assert v.llm_input is not None
    assert "AI 多轮对话（可继续追问）" in texts(v._frame)


def test_container_resize_refreshes_wraplength(tk_root):
    """接到容器 resize 通知时，气泡 wraplength 与当前可用宽度步调一致。"""
    v = make_view(tk_root)
    v.render([{"role": "assistant", "content": "body"}], loading=False)
    v._on_container_resize()
    b = bubble_labels(v._frame)[0]
    assert v._wrap_width() >= 120
    assert b.cget("wraplength") == v._wrap_width()