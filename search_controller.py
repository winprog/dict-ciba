"""搜索分流控制（P2-3）。

从 galaxy dict UI 中解耦「查询调度」：决定输入走 iciba 词典查询还是走 LLM，
并在线程中异步获取数据，把结果/错误通过回调抛回给调用方（UI 负责线程安全与渲染）。
"""

import threading
from iciba import query_word


class SearchController:
    """输入分流 + 异步查询调度。"""

    def __init__(self):
        self._query = query_word

    @staticmethod
    def _phrase_is_good(data, word):
        """判断 iciba 短语翻译是否真的有效。"""
        if data.get("result_type") == "keyword_detection":
            return False
        if data.get("word") and data["word"] != word and data["word"] in ("在线翻译",):
            return False
        if not data.get("translation"):
            return False
        return True

    def get(self, word, on_result, on_llm, on_error):
        """分流并调度查询。

        - 单词：iciba 词典查询，成功 -> on_result(data)，失败 -> on_error(ex)
        - 长文本：直接走 LLM -> on_llm(word)
        - 短语：先试 iciba，有效 -> on_result(data)，否则 -> on_llm(word)

        回调在后台线程触发，调用方需自行转到主线程更新 UI。
        """
        is_multi_word = len(word.split()) >= 2
        is_long_text = len(word) > 80

        if not is_multi_word:
            def _query_word():
                try:
                    data = self._query(word)
                    on_result(data)
                except Exception as ex:
                    on_error(ex)
            threading.Thread(target=_query_word, daemon=True).start()
            return

        if is_long_text:
            on_llm(word)
            return

        def _query_phrase():
            iciba_data = None
            try:
                iciba_data = self._query(word)
            except Exception:
                iciba_data = None
            if iciba_data and self._phrase_is_good(iciba_data, word):
                on_result(iciba_data)
            else:
                on_llm(word)

        threading.Thread(target=_query_phrase, daemon=True).start()