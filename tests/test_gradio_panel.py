"""Gradio 面板原型（gradio_panel）的单元测试。

只覆盖不依赖 gradio 的纯逻辑（history 折叠/还原、未安装时的报错契约），
并锁定顶层 import 不会因缺 gradio 而失败。
"""
import pytest

from services.gradio_panel import (
    FORMULA_BLOCK_HINT,
    GRADIO_REQUIRED_HINT,
    build_app,
    guard_inline_variables,
    expand_soft_breaks,
    render_multimath,
    to_chat_messages,
    to_gradio_history,
    with_formula_hint,
)


def test_with_formula_hint_appends_block_guidance():
    assert with_formula_hint("base").startswith("base")
    assert FORMULA_BLOCK_HINT in with_formula_hint("base")
    assert "$$" in FORMULA_BLOCK_HINT


def test_guard_escapes_variable_underscores_in_prose():
    r = guard_inline_variables("考虑 a_i 与 x_1，以及 C_{n}^{k}")
    assert r == "考虑 a\\_i 与 x\\_1，以及 C\\_{n}^{k}"


def test_guard_keeps_underscores_in_block_and_code_untouched():
    r = guard_inline_variables("公式 $$a_i + b_2$$ 块内，行内代码 `a_i` 保留")
    assert "$$a_i + b_2$$" in r
    assert "`a_i`" in r
    # 块外段落中的变量仍被转义
    assert "块内，" in r


def test_guard_keeps_real_italic_emphasis():
    r = guard_inline_variables("这是 *斜体* 与 _强调_ 的测试")
    assert r == "这是 *斜体* 与 _强调_ 的测试"


def test_render_inline_variable_into_image():
    r = render_multimath("二次项系数为 C_{n}^{k}，以及 $a_i^2$ 变量")
    assert "![](" in r
    assert "$a_i^2$" not in r
    # 未被公式包裹的段落下标仍由 guard 兜底，render 本身不动它
    assert "C_{n}^{k}" in r


def test_render_block_into_image():
    r = render_multimath("$$\\sum_{i=1}^{n} a_i^2$$，块级公式")
    assert "![](" in r
    assert "$$" not in r


def test_render_preserves_plain_text():
    assert render_multimath("没有公式的普通文字 a_i 保持原样") == "没有公式的普通文字 a_i 保持原样"


def test_render_failure_preserves_original():
    # 非法 LaTeX -> matplotlib 抛错 -> 原样保留，不破坏消息
    r = render_multimath("坏公式 $\\left(未闭合$ 后面文字")
    assert isinstance(r, str)
    assert "文字" in r


def test_render_svg_uses_current_color_for_theme():
    # 字形缺省黑色；注入 currentColor 让公式跟随主题文字色（暗色主题不发黑）
    import base64
    import re

    out = render_multimath("主题色 $a_i$")
    uri = re.search(r"data:image/svg\+xml;base64,[^)]+", out).group()
    svg = base64.b64decode(uri.replace("data:image/svg+xml;base64,", "")).decode()
    assert 'fill="currentColor"' in svg


def test_expand_soft_breaks_inserts_markdown_newline():
    # 单换行 -> 变成软换行（行尾两空格 + 换行），gradio 才会换行
    r = expand_soft_breaks("第一行\n第二行")
    assert "第一行  \n第二行" in r


def test_expand_soft_breaks_keeps_paragraph_blank_line():
    # 段落间本就有空行（连续换行）应保持不变
    r = expand_soft_breaks("第一段\n\n第二段")
    assert r == "第一段\n\n第二段"


def test_expand_soft_breaks_protects_code_and_formula():
    src = "```\ndef f():\n    return 1\n```\n后面\n$\\sum$"
    r = expand_soft_breaks(src)
    # 代码块内部换行原样保留
    assert "def f():\n    return 1" in r
    # 代码块之后、以及公式之后的普通单换行 -> 软换行
    assert "  \n后面" in r


def test_to_gradio_history_pairs_user_bot():
    history = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2"},
    ]
    assert to_gradio_history(history) == [["Q1", "A1"], ["Q2", "A2"]]


def test_to_gradio_history_trailing_user():
    # 末尾多余 user（AI 思考中，尚未回答）单独成行
    history = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
    ]
    assert to_gradio_history(history) == [["Q1", "A1"], ["Q2", ""]]


def test_to_chat_messages_reconstructs_and_appends():
    gradio_h = [["Q1", "A1"], ["Q2", "A2"]]
    msgs = to_chat_messages(gradio_h, latest_user="Q3")
    assert msgs == [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2"},
        {"role": "user", "content": "Q3"},
    ]


def test_to_chat_messages_empty_latest():
    assert to_chat_messages([], latest_user="") == []


def test_build_app_errors_without_gradio():
    # gradio 未安装时给出可操作的安装提示而不是裸 ImportError
    try:
        import gradio  # noqa: F401  已安装则走构建分支
    except ImportError:
        with pytest.raises(RuntimeError) as exc:
            build_app(chat=lambda m, **k: "x", system_prompt="s")
        assert GRADIO_REQUIRED_HINT in str(exc.value)
        return


def test_build_app_builds_demo_with_gradio():
    """装了 gradio 时能真正构建出 Blocks 应用（用于启动/浏览器打开）。"""
    pytest.importorskip("gradio")
    demo = build_app(chat=lambda m, **k: "ok", system_prompt="s")
    assert demo is not None