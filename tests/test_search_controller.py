"""SearchController 的单元测试。

覆盖静态『短语是否有效』判定与 get() 的分流调度。get() 的异步分支用
Event 同步；注入假 _query 替换真实 iciba 查询，不触碰网络。
"""
import threading

from search_controller import SearchController


# ---- _phrase_is_good 纯逻辑 ----

def test_phrase_is_good_rejects_keyword_detection():
    data = {"result_type": "keyword_detection", "translation": "有内容"}
    assert SearchController._phrase_is_good(data, "hello") is False


def test_phrase_is_good_rejects_empty_translation():
    data = {"result_type": "phrase_translation", "translation": ""}
    assert SearchController._phrase_is_good(data, "hello") is False


def test_phrase_is_good_rejects_online_translation_marker():
    data = {"result_type": "phrase_translation", "word": "在线翻译", "translation": "x"}
    assert SearchController._phrase_is_good(data, "hello") is False


def test_phrase_is_good_accepts_valid():
    data = {"result_type": "phrase_translation", "word": "look up", "translation": "查阅"}
    assert SearchController._phrase_is_good(data, "look up") is True


# ---- get() 分流调度 ----

def _make_callbacks():
    results, llms, errors = [], [], []
    done = threading.Event()

    def _finish():
        done.set()

    def on_result(d):
        results.append(d); _finish()
    def on_llm(w):
        llms.append(w); _finish()
    def on_error(e):
        errors.append(e); _finish()

    return results, llms, errors, done


def test_word_queries_and_results():
    sentinel = {"word": "abandon"}
    c = SearchController()
    c._query = lambda w: sentinel
    results, llms, errors, done = _make_callbacks()
    c.get("abandon", on_result=lambda d: (results.append(d), done.set()),
                      on_llm=lambda w: (llms.append(w), done.set()),
                      on_error=lambda e: (errors.append(e), done.set()))
    assert done.wait(2)
    assert results == [sentinel]
    assert llms == []


def test_word_query_error_routes_to_on_error():
    c = SearchController()
    boom = RuntimeError("net")
    def failing(w):
        raise boom
    c._query = failing
    results, llms, errors, done = _make_callbacks()
    c.get("abandon", on_result=lambda d: (results.append(d), done.set()),
                      on_llm=lambda w: (llms.append(w), done.set()),
                      on_error=lambda e: (errors.append(e), done.set()))
    assert done.wait(2)
    assert errors == [boom]


def test_long_text_direct_to_llm_without_query():
    calls = []
    c = SearchController()
    def counting(w):
        calls.append(w)
        return {}
    c._query = counting
    results, llms, errors, done = _make_callbacks()
    long_word = "w" * 90
    c.get(long_word, on_result=lambda d: (results.append(d), done.set()),
                     on_llm=lambda w: (llms.append(w), done.set()),
                     on_error=lambda e: (errors.append(e), done.set()))
    assert llms == [long_word]           # 同步路径
    assert calls == []                   # 未发起 iciba 查询


def test_phrase_valid_uses_iciba_result():
    data = {"word": "look up", "translation": "查阅"}
    c = SearchController()
    c._query = lambda w: data
    results, llms, errors, done = _make_callbacks()
    c.get("look up", on_result=lambda d: (results.append(d), done.set()),
                     on_llm=lambda w: (llms.append(w), done.set()),
                     on_error=lambda e: (errors.append(e), done.set()))
    assert done.wait(2)
    assert results == [data]
    assert llms == []


def test_phrase_invalid_falls_to_llm():
    c = SearchController()
    c._query = lambda w: {"word": "look up", "translation": ""}
    results, llms, errors, done = _make_callbacks()
    c.get("look up", on_result=lambda d: (results.append(d), done.set()),
                     on_llm=lambda w: (llms.append(w), done.set()),
                     on_error=lambda e: (errors.append(e), done.set()))
    assert done.wait(2)
    assert results == []
    assert llms == ["look up"]


def test_phrase_query_exception_falls_to_llm():
    c = SearchController()
    def failing(w):
        raise RuntimeError("boom")
    c._query = failing
    results, llms, errors, done = _make_callbacks()
    c.get("look up", on_result=lambda d: (results.append(d), done.set()),
                     on_llm=lambda w: (llms.append(w), done.set()),
                     on_error=lambda e: (errors.append(e), done.set()))
    assert done.wait(2)
    assert llms == ["look up"]           # 错误降级走 LLM
    assert errors == []