"""WordStateManager 的单元测试。

WordStateManager 是全项目中"单词清洗 + 新旧判定"的纯逻辑接缝，不依赖
Tk/显示环境。以下用已知正确的手写字面量作为独立事实来源断言（避免自证）。
"""
import pytest

from word_state_manager import WordStateManager


@pytest.fixture
def manager():
    return WordStateManager()


# ---- clean_punctuation ----

@pytest.mark.parametrize("raw,expected", [
    # 英文标点
    ('"Hello!"', 'Hello'),
    ("What's it", "What's it"),   # 内部撇号保留
    ('word...', 'word'),
    ('(paren)', 'paren'),
    ('[bracket]', 'bracket'),
    # 中文标点
    ('，世界。', '世界'),
    ('《书名》', '书名'),
    ('“引号”', '引号'),
    # 纯标点 -> 空
    ('!!!', ''),
    ('。。。', ''),
    # 无标点原样（含两端空格被 strip）
    ('abc', 'abc'),
    ('  spaced  ', 'spaced'),
    ('word-end', 'word-end'),     # 连字符不在清理集内
])
def test_clean_punctuation_literals(manager, raw, expected):
    assert manager.clean_punctuation(raw) == expected


def test_clean_punctuation_handles_empty_and_none(manager):
    assert manager.clean_punctuation("") == ""
    assert manager.clean_punctuation(None) is None


# ---- handle_new_word ----

def test_new_word_returns_process(manager):
    result = manager.handle_new_word("LLM")
    assert result["should_process"] is True
    assert result["reason"] == "new_word"
    assert result["cleaned_word"] == "LLM"
    assert result["is_same_word"] is False


def test_empty_after_cleaning_skips(manager):
    result = manager.handle_new_word("!!!")
    assert result["should_process"] is False
    assert result["reason"] == "empty_after_cleaning"


def test_punctuated_repeat_is_same_word(manager):
    # 先命中一个词，再带标点命中同一词 -> 视为相同，不处理
    manager.handle_new_word("LLM")
    result = manager.handle_new_word("LLM.")
    assert result["should_process"] is False
    assert result["reason"] == "same_word"
    assert result["is_same_word"] is True


def test_different_word_triggers_again(manager):
    manager.handle_new_word("LLM")
    result = manager.handle_new_word("AI")
    assert result["should_process"] is True
    assert result["reason"] == "new_word"
    assert result["cleaned_word"] == "AI"


def test_handle_new_word_updates_internal_state(manager):
    manager.handle_new_word("LLM")
    assert manager.current_word == "LLM"
    assert manager.last_captured_word == "LLM"
    r2 = manager.handle_new_word("AI")
    assert manager.current_word == "AI"
    assert manager.last_captured_word == "AI"
    assert r2["reason"] == "new_word"