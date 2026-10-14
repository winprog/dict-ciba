"""spinner.make_spinner 的 Tk 实渲染测试。"""
import tkinter as tk

import pytest

from spinner import make_spinner


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    yield root
    root.destroy()


def test_creates_label_with_text(tk_root):
    label, stop = make_spinner(tk_root, "loading...")
    try:
        assert isinstance(label, tk.Label)
        assert "loading..." in label.cget("text")
        assert label in tk_root.winfo_children()
    finally:
        stop()


def test_initial_glyph_is_from_flag_set(tk_root):
    label, stop = make_spinner(tk_root, "t")
    try:
        glyph = label.cget("text")[0]
        assert glyph in "|-/\\"
    finally:
        stop()


def test_stop_destroys_label(tk_root):
    label, stop = make_spinner(tk_root, "x")
    stop()
    assert label not in tk_root.winfo_children()


def test_stop_is_idempotent(tk_root):
    label, stop = make_spinner(tk_root, "x")
    stop()
    stop()          # 二次调用不抛异常
    assert label not in tk_root.winfo_children()