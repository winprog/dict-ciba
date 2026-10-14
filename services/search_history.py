"""搜索历史持久化（P3-4）。

用本地 JSON 保存最近 20 条搜索词，供输入框 Combobox 下拉复用。
存储失败（权限/磁盘）静默降级，不影响查词主流程。
"""

import json
import os

try:
    from services.logger import get_logger
except Exception:  # 独立运行兜底
    import logging
    get_logger = logging.getLogger


class SearchHistory:
    """最近搜索词的有序去重列表（最近优先）。

    线程安全说明：仅在 GUI 主线程读写，无需加锁。
    """

    MAX = 20

    def __init__(self, path=None):
        self.path = path or os.path.expanduser("~/.ciba_history.json")
        self._log = get_logger(__name__)
        self._items = []
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._items = [str(w) for w in raw if w][: self.MAX]
        except Exception:
            self._items = []

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False)
        except Exception as e:
            self._log.warning(f"SearchHistory 保存失败: {e}")

    def add(self, word):
        """记录一条搜索词（去重后前插，最多保留 MAX 条）。"""
        word = str(word).strip()
        if not word:
            return
        if word in self._items:
            self._items.remove(word)
        self._items.insert(0, word)
        if len(self._items) > self.MAX:
            del self._items[self.MAX:]
        self._save()

    def list(self):
        return list(self._items)