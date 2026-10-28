"""markdown 结构化块解析。

把 LLM 回答文本切分成两类块，供 LLM 气泡按块渲染：
- text:  普通文本块（保持原样，交由上层做纯文本降级）
- table: markdown 表格块（表头 header + 行 rows，均为字符串单元格列表）

规则（对齐常见 markdown 表格子集）：
- 一个表格 = 头行 + 紧随其后的分隔行（| :--- |） + 可选的若干正文行
- 分隔行内容形如 :?-+:?，与表头行数无关的甄别在本函数做；无正文也判定为表格
- 仅含 | 但没有分隔行跟随的行不视为表格，归入文本块
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Block:
    kind: str                 # "text" | "table"
    content: Optional[str] = None   # kinds, 仅 text
    header: Optional[List[str]] = None  # 仅 table
    rows: Optional[List[List[str]]] = None  # 仅 table


def _is_separator(line: str) -> bool:
    """判断是否为 markdown 表格分隔行，如 | :--- | :--- |"""
    stripped = line.strip()
    if not stripped or not stripped.startswith("|"):
        return False
    inner = stripped.strip("|")
    cells = [c.strip() for c in inner.split("|")]
    cells = [c for c in cells if c != ""]
    if not cells:
        return False
    for c in cells:
        if not c.replace(":", "-").strip("-") == "":   # 仅由 - 和 : 组成
            return False
    return True


def _split_row(line: str) -> List[str]:
    stripped = line.strip()
    inner = stripped.strip("|")
    return [c.strip() for c in inner.split("|")]


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def split_blocks(text: str) -> List[Block]:
    lines = text.splitlines(keepends=True)
    # 非 keepends 拆行以便处理粘连文本，行尾换行由块拼接时保留
    blocks: List[Block] = []
    text_buf: List[str] = []

    def flush_text():
        if text_buf:
            while text_buf and not text_buf[0].strip():
                text_buf.pop(0)
            while text_buf and not text_buf[-1].strip():
                text_buf.pop()
            if text_buf:
                content = "\n".join(t.rstrip("\n") for t in text_buf)
                if content:
                    blocks.append(Block(kind="text", content=content))
            text_buf.clear()

    def is_table_start(idx: int) -> Optional[int]:
        """若 lines[idx] 处是一个表格块，返回其在 blocks 列表中追加后的结束 idx；否则 None"""
        if not _is_table_row(lines[idx]):
            return None
        if idx + 1 >= len(lines):
            return None
        if not _is_separator(lines[idx + 1]):
            return None
        return idx + 1

    i = 0
    n = len(lines)
    while i < n:
        row_line = lines[i].rstrip("\n")
        sep_idx = is_table_start(i) if row_line else None
        if sep_idx is not None:
            flush_text()
            header = _split_row(row_line)
            rows: List[List[str]] = []
            j = sep_idx + 1
            while j < n and _is_table_row(lines[j]):
                rows.append(_split_row(lines[j]))
                j += 1
            blocks.append(Block(kind="table", header=header, rows=rows))
            i = j
        else:
            text_buf.append(lines[i])
            i += 1
    flush_text()
    return blocks