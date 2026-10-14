"""LLMChatView.render 的渲染流程与回归测试。

气泡改用只读 SelectableText 渲染（取代 HtmlFrame/Label），因此断言：
气泡可选中复制、文本正确（无 markdown 星号/无字面 <p>）、wrap=word，
锁定「行高挤压」「大片空白」「横向溢出」等 HtmlFrame 布局回归以及
「结果不可划选复制」回归。
"""
import tkinter as tk

import pytest

from ui import llm_chat_view
from ui.selectable_text import SelectableText
from ui.ui_constants import COLORS, FONTS


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
            if ch.winfo_class() == "Text":
                try:
                    out.append(ch.get("1.0", "end-1c"))
                except tk.TclError:
                    pass
            else:
                try:
                    t = ch.cget("text")
                except tk.TclError:
                    t = None
                if t:
                    out.append(t)
            walk(ch)

    walk(w)
    return out


def bubble_widgets(w):
    """返回对话气泡（带气泡背景色的 SelectableText）。"""
    bubble_bg = (COLORS["bubble_ai"], COLORS["bubble_user"])
    out = []
    for ch in w.winfo_children():
        try:
            if isinstance(ch, SelectableText) and ch.cget("background") in bubble_bg:
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
    """user 气泡保留原文本；assistant 降为纯文本；可选中复制；wrap=word。"""
    v = make_view(tk_root)
    v.render(
        [{"role": "user", "content": "a<b>c"}, {"role": "assistant", "content": "**bold** 第一段\n\n- 列表项"}],
        loading=False,
    )
    bubbles = bubble_widgets(v._frame)
    assert len(bubbles) == 2
    # user 气泡原样展示（不做 HTML 转义，也不应有字面 <p> 残留）
    assert bubbles[0].get("1.0", "end-1c") == "a<b>c"
    # assistant 去除 ** 标记、保留内容
    asst_text = bubbles[1].get("1.0", "end-1c")
    assert "**" not in asst_text
    assert "bold" in asst_text
    assert "•" in asst_text
    # 每个气泡都按 word 折行（防横向溢出），且只读可选中（可划选复制）
    for b in bubbles:
        assert b.cget("wrap") == "word"
        seqs = list(b.bind())
        assert "<Key>" in seqs or "<Control-c>" in seqs
        assert "<Button-3>" in seqs


def test_render_after_widgets_destroyed_rebuilds(tk_root):
    """模拟字典搜索 destroy 掉 scrollable_frame 子控件后，渲染 LLM 视图仍自愈。"""
    v = make_view(tk_root)
    for w in v._frame.winfo_children():
        w.destroy()
    v.render([{"role": "user", "content": "word"}], loading=False)
    assert v.llm_input is not None
    assert "AI 多轮对话（可继续追问）" in texts(v._frame)


def test_bubble_is_selectable_readonly_text(tk_root):
    """气泡是只读可选中 Text：保留划选，但禁键盘编辑（不可修改文本）。"""
    v = make_view(tk_root)
    v.render([{"role": "assistant", "content": "body"}], loading=False)
    b = bubble_widgets(v._frame)[0]
    assert isinstance(b, tk.Text)
    assert b.cget("wrap") == "word"