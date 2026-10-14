"""ResultRenderer.render 的 Tk 实渲染测试。

在真实 Tk 根上渲染样例 data，验证各分支不抛异常、换行登记正确、
关键文本确实呈现。这层专治 LEFT『NameError』这类只在真实渲染路径
才暴露的缺陷。无显示环境时自动 skip。
"""
import tkinter as tk

import pytest

from result_renderer import ResultRenderer


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
    """收集渲染目标 frame 下的文本（递归），用于行为断言。"""
    out = []

    def walk(w):
        for child in w.winfo_children():
            try:
                txt = child.cget("text")
                if txt:
                    out.append(txt)
            except tk.TclError:
                pass
            walk(child)

    walk(renderer.frame)
    return out


def test_long_text_branch(tk_root):
    r = make_renderer(tk_root)
    r.render({"word": "x" * 120, "is_phrase": False})
    assert r._wrap_labels                      # 已登记换行
    assert "x" * 120 in render_texts(r)


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


def test_update_wraplength_applies_wrap(tk_root):
    r = make_renderer(tk_root)
    r.render({"word": "translate"})
    r.update_wraplength(600)
    # 登记的 label 都应被更新为指定 wrap 宽度
    for label, _ in r._wrap_labels:
        assert label.cget("wraplength") in (max(120, 600 - 20), max(90, 600 - 50))