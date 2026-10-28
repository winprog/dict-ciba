"""TableWidget（表格网格渲染）的单元测试。

锁定 LLM 回答里 markdown 表格能渲染成对齐的 Tk 网格：
- 表头行 + 数据行逐格渲染，单元格文本正确、缺列补空白
- 表头加粗，其余为正文
- 每格为可划选复制的只读 SelectableText（exportselection=False）
"""
import tkinter as tk

import pytest

from ui.selectable_text import SelectableText
from ui.table_widget import TableWidget


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    yield root
    root.destroy()


def make_table(root, header, rows):
    f = tk.Frame(root)
    f.pack()
    return TableWidget(f, header=header, rows=rows), f


def cell_texts(cells):
    return [c.get("1.0", "end-1c") for c in cells]


def test_header_and_rows_rendered(tk_root):
    t, _ = make_table(
        tk_root,
        header=["A", "B", "C"],
        rows=[["1", "2", "3"], ["4", "5", "6"]],
    )
    assert cell_texts(t.header_cells) == ["A", "B", "C"]
    assert cell_texts(t.cells) == ["1", "2", "3", "4", "5", "6"]


def test_ragged_row_padded_with_blank_cell(tk_root):
    t, _ = make_table(tk_root, header=["A", "B", "C"], rows=[["4", "5"]])
    assert cell_texts(t.cells) == ["4", "5", " "]


def test_header_uses_bold_font(tk_root):
    """表头单元格带 bold 字样（Tk 把字体元组规范化为字体串）。"""
    t, _ = make_table(tk_root, header=["A", "B"], rows=[["1"]])
    for c in t.header_cells:
        assert "bold" in str(c.cget("font"))


def test_body_cells_use_regular_font(tk_root):
    t, _ = make_table(tk_root, header=["A", "B"], rows=[["1", "2"]])
    for c in t.cells:
        assert "bold" not in str(c.cget("font"))


def test_every_cell_is_selectable_readonly(tk_root):
    """表头与数据单元格都是可划选复制的只读 SelectableText。"""
    t, _ = make_table(tk_root, header=["A", "B"], rows=[["1", "2"], ["3", "4"]])
    for cell in list(t.header_cells) + list(t.cells):
        assert isinstance(cell, SelectableText)
        assert cell.cget("exportselection") == 0