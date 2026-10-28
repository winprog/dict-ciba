"""只读表格网格控件（TableWidget）。

把 markdown 表格块（表头 + 行）渲染成对齐的 Tk 网格：
- 每格一个只读 SelectableText（可划选复制）
- 表头加粗，正文常规
- 列通过 grid 的 uniform+weight 均匀等分；缺列补空白格以保持对齐
"""
from typing import List

import tkinter as tk

from ui.selectable_text import SelectableText
from ui.ui_constants import COLORS, FONTS


class TableWidget(tk.Frame):
    """渲染表头 + 数据行的只读表格。"""

    def __init__(self, master, header: List[str], rows: List[List[str]]):
        super().__init__(
            master, bg=COLORS["bubble_ai"],
            bd=1, relief="solid", highlightthickness=0,
        )
        self.header_cells: List[SelectableText] = []
        self.cells: List[SelectableText] = []
        self._build(list(header), [list(r) for r in rows])

    def _build(self, header, rows):
        ncols = max(len(header), *(len(r) for r in rows or [[]]))
        for c in range(ncols):
            self.columnconfigure(c, uniform="col", weight=1, minsize=60)
        for r in range(len(rows) + 1):
            self.rowconfigure(r, weight=1)

        for c in range(ncols):
            text = header[c] if c < len(header) else ""
            cell = self._cell(text, font=FONTS["body_bold"], bg=COLORS["card"])
            cell.grid(row=0, column=c, sticky="nsew")
            self.header_cells.append(cell)

        for r, row in enumerate(rows, start=1):
            for c in range(ncols):
                text = row[c] if c < len(row) else ""
                cell = self._cell(text, font=FONTS["body"], bg=COLORS["surface"])
                cell.grid(row=r, column=c, sticky="nsew")
                self.cells.append(cell)

    def _cell(self, text, *, font, bg):
        return SelectableText(
            self, text or " ", font=font, fg=COLORS["bubble_ai_text"], bg=bg, pad=6,
        )