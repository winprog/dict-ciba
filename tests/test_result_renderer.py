"""ResultRenderer.render 的 Tk 实渲染测试。

在真实 Tk 根上渲染样例 data，验证各分支不抛异常、关键文本确实呈现、
文本控件可选中复制。这层专治 LEFT『NameError』这类只在真实渲染路径
才暴露的缺陷。无显示环境时自动 skip。
"""
import tkinter as tk

import pytest

from ui.result_renderer import ResultRenderer
from ui.selectable_text import SelectableText


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    yield root
    root.destroy()


def make_renderer(root):
    frame = tk.Frame(root)
    frame.pack()
    return ResultRenderer(frame, get_frame_width=lambda: 800)


def render_texts(renderer):
    """收集渲染目标 frame 下的文本（递归，兼容 Label 与 SelectableText）。"""
    out = []

    def walk(w):
        for child in w.winfo_children():
            if child.winfo_class() == "Text":
                try:
                    out.append(child.get("1.0", "end-1c"))
                except tk.TclError:
                    pass
            else:
                try:
                    txt = child.cget("text")
                    if txt:
                        out.append(txt)
                except tk.TclError:
                    pass
            walk(child)

    walk(renderer.frame)
    return out


def text_widgets(w):
    """收集 frame 下所有 SelectableText 控件（递归）。"""
    out = []

    def walk(x):
        for child in x.winfo_children():
            if isinstance(child, SelectableText):
                out.append(child)
            walk(child)

    walk(w)
    return out


def test_rendered_text_widgets_are_selectable(tk_root):
    """文本由只读可选中 Text 承载，锁定「结果可划选复制」回归。"""
    r = make_renderer(tk_root)
    r.render({
        "word": "hello", "is_phrase": False,
        "symbols": {"parts": [{"part": "int.", "means": ["你好", "问候"]}]},
    })
    texts = text_widgets(r.frame)
    assert texts, "结果应渲染为可选中文本控件"
    for w in texts:
        assert isinstance(w, tk.Text)
        seqs = list(w.bind())
        assert "<Key>" in seqs or "<Control-c>" in seqs


def test_long_text_branch(tk_root):
    r = make_renderer(tk_root)
    r.render({"word": "x" * 120, "is_phrase": False})
    assert any("x" * 120 == t for t in render_texts(r))
    assert text_widgets(r.frame), "长文本应以可选中 Text 承载"


def test_phrase_translation_branch(tk_root):
    r = make_renderer(tk_root)
    r.render({
        "word": "look up", "result_type": "phrase_translation", "is_phrase": True,
        "translation": "查阅", "from_language": "en", "to_language": "zh",
        "suggestion": "",
    })
    texts = render_texts(r)
    assert "look up" in texts
    assert "翻译:" in texts
    assert "查阅" in texts


def test_llm_translation_branch(tk_root):
    r = make_renderer(tk_root)
    r.render({
        "word": "hello", "result_type": "llm_translation", "is_phrase": True,
        "translation": "AI 返回值", "from_language": "en", "to_language": "zh",
    })
    assert "AI 翻译:" in render_texts(r)


def test_word_with_pronounce_buttons_branch(tk_root):
    """覆盖曾触发 LEFT NameError 的音标按钮路径。"""
    r = make_renderer(tk_root)
    r.render({
        "word": "abandon", "result_type": "dictionary", "is_phrase": False,
        "symbols": {
            "word_symbol": "abandon",
            "ph_en": "/ə'bændən/", "ph_am": "/ə'bændən/",
            "ph_en_mp3": "http://x/e.mp3", "ph_am_mp3": "http://x/a.mp3",
            "ph_tts_mp3": "http://x/t.mp3",
            "parts": [
                {"part": "v.", "means": ["放弃", "抛弃"]},
                {"part": "n.", "means": ["放任"]},
            ],
        },
    })
    texts = render_texts(r)
    assert "EN: /ə'bændən/" in texts
    assert "AM: /ə'bændən/" in texts
    assert "🔊 TTS" in texts
    assert "v.:" in texts
    assert any("放弃, 抛弃" in t for t in texts)


def test_update_wraplength_is_noop(tk_root):
    r = make_renderer(tk_root)
    r.render({"word": "translate"})
    r.update_wraplength(600)               # 换行现由 SelectableText 自动处理，不应抛异常
    assert text_widgets(r.frame)