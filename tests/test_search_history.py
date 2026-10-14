"""SearchHistory 的单元测试。

用独立可写的临时文件（tmp_path）注入 path，验证持久化往返、有序去重与
MAX 截断。事实来源是手写顺序/次数字面量。
"""
import json

import pytest

from services.search_history import SearchHistory


def test_add_recent_first(tmp_path):
    h = SearchHistory(path=str(tmp_path / "h.json"))
    h.add("apple")
    h.add("banana")
    assert h.list() == ["banana", "apple"]


def test_add_dedup_moves_to_front(tmp_path):
    h = SearchHistory(path=str(tmp_path / "h.json"))
    h.add("apple")
    h.add("banana")
    h.add("apple")
    assert h.list() == ["apple", "banana"]


def test_blank_and_whitespace_ignored(tmp_path):
    h = SearchHistory(path=str(tmp_path / "h.json"))
    h.add("   ")
    h.add("")
    assert h.list() == []


def test_capped_at_max(tmp_path):
    h = SearchHistory(path=str(tmp_path / "h.json"))
    for i in range(25):
        h.add(f"word{i}")
    items = h.list()
    assert len(items) == SearchHistory.MAX == 20
    assert items[0] == "word24"          # 最近的在最前
    assert "word0" not in items          # 最旧的被裁剪


def test_persists_across_instances(tmp_path):
    path = str(tmp_path / "h.json")
    h1 = SearchHistory(path=path)
    h1.add("apple")
    h1.add("banana")

    h2 = SearchHistory(path=path)        # 新实例从磁盘恢复
    assert h2.list() == ["banana", "apple"]


def test_corrupt_file_degrades_to_empty(tmp_path):
    path = str(tmp_path / "h.json")
    path = tmp_path / "h.json"
    path.write_text("{ not valid json", encoding="utf-8")
    h = SearchHistory(path=str(path))
    assert h.list() == []


def test_persists_unicode(tmp_path):
    path = str(tmp_path / "h.json")
    h = SearchHistory(path=str(path))
    h.add("你好")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    assert "你好" in raw