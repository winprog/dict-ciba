"""markdown 列块解析器（split_blocks）的单元测试。

锁定 LLM 回答里 markdown「表格」能被识别并拆成结构化块：
- 普通文本/前面后文本原样保留（TextBlock）
- 表格块（TableBlock）带表头与行单元格，分隔行 | :--- | 被丢弃
- 含 | 但不是表格（无分隔行）的内容不应误判为表格
"""
from ui.markdown_blocks import split_blocks


def test_plain_text_single_block():
    """纯文本整体为一个文本块，行以换行连接，首尾不留空行。"""
    blocks = split_blocks("hello\nworld\n")
    assert len(blocks) == 1
    assert blocks[0].kind == "text"
    assert blocks[0].content == "hello\nworld"


def test_empty_input_yields_no_blocks():
    blocks = split_blocks("")
    assert blocks == []


def test_table_header_and_rows_parsed():
    md = (
        "| 生物学概念 | 软件工程类比（近似） | 说明 |\n"
        "| :--- | :--- | :--- |\n"
        "| 基因拷贝数 (Dosage) | 代码行数/线程数 | 更多副本=更多处理 |\n"
        "| 基因突变 (Mutation) | 代码Bug/版本错误 | 某段代码有Bug |\n"
    )
    blocks = split_blocks(md)
    assert len(blocks) == 1
    t = blocks[0]
    assert t.kind == "table"
    assert t.header == ["生物学概念", "软件工程类比（近似）", "说明"]
    assert t.rows == [
        ["基因拷贝数 (Dosage)", "代码行数/线程数", "更多副本=更多处理"],
        ["基因突变 (Mutation)", "代码Bug/版本错误", "某段代码有Bug"],
    ]


def test_rows_with_ragged_cell_count_kept():
    md = (
        "| a | b |\n"
        "| --- | --- |\n"
        "| 1 | 2 |\n"
        "| 3 |\n"
    )
    t = split_blocks(md)[0]
    assert t.kind == "table"
    assert t.header == ["a", "b"]
    assert t.rows == [["1", "2"], ["3"]]


def test_text_preserved_around_table():
    """表格前后的文本块原样保留（去掉自身首尾空行），块间空白归入邻近文本块。"""
    md = "前言\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n结语\n"
    blocks = split_blocks(md)
    kinds = [b.kind for b in blocks]
    assert kinds == ["text", "table", "text"]
    assert blocks[0].content == "前言"
    assert blocks[2].content == "结语"


def test_pipe_line_without_separator_is_not_table():
    md = "这行有 | 管道但\n下面是没有分隔的\n继续文本\n"
    blocks = split_blocks(md)
    assert len(blocks) == 1
    assert blocks[0].kind == "text"


def test_table_without_body_rows():
    """表头 + 分隔行、无正文时，判为一个空表（rows 为空）。"""
    md = "| a | b |\n| --- | --- |\n"
    blocks = split_blocks(md)
    assert len(blocks) == 1
    t = blocks[0]
    assert t.kind == "table"
    assert t.header == ["a", "b"]
    assert t.rows == []


def test_two_tables_separated_by_text():
    md = (
        "| a | b |\n| --- | --- |\n| 1 | 2 |\n\n段落\n\n"
        "| c | d |\n| --- | --- |\n| 3 | 4 |\n"
    )
    kinds = [b.kind for b in split_blocks(md)]
    assert kinds == ["table", "text", "table"]