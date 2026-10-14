"""SelectableText 控件语义回归测试。

锁定「结果可划选复制」与「划选不触发全局取词」两条关键行为：
- exportselection=False：划选不导出 X PRIMARY，避免被取词服务轮询误判为划词
- 只读：键盘编辑被拦（_block_key），文本内容不受输入影响
- 复制能力：<Key> 读、<Button-3> 右键菜单绑定仍存在
- 高度贴合：height 与换行后 displaylines 一致（无大片空白）
"""
import types

import tkinter as tk

import pytest

from ui.selectable_text import _block_key, SelectableText


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    yield root
    root.destroy()


def test_export_selection_is_off(tk_root):
    """划选不导出 PRIMARY，全局取词服务读不到结果区选区 → 不误触发取词。"""
    f = tk.Frame(tk_root)
    w = SelectableText(f, "hello world", font=("Arial", 13), fg="black")
    assert int(w.cget("exportselection")) == 0, "结果区划选不应导出 PRIMARY"


def test_copy_bindings_present(tk_root):
    """保留复制能力：<Key> 过滤与右键菜单绑定都在。"""
    f = tk.Frame(tk_root)
    w = SelectableText(f, "hello world", font=("Arial", 13), fg="black")
    seqs = list(w.bind())
    assert "<Key>" in seqs
    assert "<Button-3>" in seqs


def test_key_block_logic():
    """_block_key：普通字符拦截（只读）；Ctrl+C/A 放行（复制/全选）；Ctrl+X/V 拦截。"""
    # 无修饰键字符输入 → break（阻止编辑）
    assert _block_key(types.SimpleNamespace(state=0, keysym="x")) == "break"
    # Ctrl+C / Ctrl+A → None（放行内建复制/全选）
    assert _block_key(types.SimpleNamespace(state=0x0004, keysym="c")) is None
    assert _block_key(types.SimpleNamespace(state=0x0004, keysym="a")) is None
    # Ctrl+V（粘贴）/ Ctrl+X（剪切）会改写文本 → break（保持只读）
    assert _block_key(types.SimpleNamespace(state=0x0004, keysym="v")) == "break"
    assert _block_key(types.SimpleNamespace(state=0x0004, keysym="x")) == "break"
    # 方向键放行（光标移动，不改变内容）
    assert _block_key(types.SimpleNamespace(state=0, keysym="Right")) is None


def test_height_matches_displaylines(tk_root):
    """高度贴合换行后的显示行数，避免文字下方大片空白。

    <Configure> 回调在布局稳定时自动贴合；这里 update 后显式触发一次
    _refit，保证断言是确定性的（不依赖定时器时机）。
    """
    root = tk_root
    root.geometry("400x500")
    host = tk.Frame(root)
    host.pack(fill="both", expand=True)
    host.configure(width=400)
    host.update_idletasks()
    text = "长文本，用于验证高度贴合：" + ("word " * 40)
    w = SelectableText(host, text, font=("Arial", 13), fg="black")
    w.pack(fill="x", anchor="w")
    for _ in range(4):
        root.update_idletasks()
        root.update()
    w._refit()  # 布局已稳定，强制贴合到真实显示行数
    h = int(w.cget("height"))
    d = int(w.tk.call(w._w, "count", "-displaylines", "1.0", "end-1c"))
    assert w.get("1.0", "end-1c") == text
    assert h == d, f"height={h} 与 displaylines={d} 不一致"