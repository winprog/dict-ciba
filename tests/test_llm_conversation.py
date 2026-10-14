"""LLMConversation 的单元测试。

用注入的假 chat（可门控阻塞）验证对话状态机、追问防抖与错误回调。
chat 与回调跑在后台线程，测试主线程用 Event 同步，避免竞态断言。
"""
import threading
import time

import pytest

from llm_conversation import LLMConversation


class Gate:
    """可阻塞/放行的门控，用于模拟 in-flight 的 LLM 请求。"""
    def __init__(self):
        self._evt = threading.Event()

    def close(self):
        self._evt.clear()

    def wait(self):
        self._evt.wait()

    def open(self):
        self._evt.set()


def make_conv(chat, system_prompt="sys"):
    answers, errors = [], []
    done = threading.Event()

    def on_answer(a):
        answers.append(a)
        done.set()

    def on_error(e):
        errors.append(e)
        done.set()

    conv = LLMConversation(
        system_prompt, chat, on_answer=on_answer, on_error=on_error
    )
    return conv, answers, errors, done


def wait_done(done, timeout=3.0):
    assert done.wait(timeout), "worker 未在超时内回调"
    return done


def wait_busy(conv, timeout=2.0):
    deadline = time.time() + timeout
    while not conv.busy and time.time() < deadline:
        time.sleep(0.01)
    return conv.busy


def test_start_sends_user_and_passes_system_prompt():
    chat_log = []
    gate = Gate(); gate.close()

    def chat(history, system_prompt=None):
        chat_log.append((list(history), system_prompt))
        gate.wait()
        return "hello"

    conv, answers, errors, done = make_conv(chat)
    conv.start("LLM")

    gate.open()
    wait_done(done)

    assert answers == ["hello"]
    assert chat_log[0][1] == "sys"                       # system_prompt 透传
    assert chat_log[0][0] == [{"role": "user", "content": "LLM"}]


def test_ask_rejected_while_busy():
    gate = Gate(); gate.close()

    def chat(history, system_prompt=None):
        gate.wait()
        return "ok"

    conv, answers, errors, done = make_conv(chat)
    conv.start("W")
    assert wait_busy(conv) is True

    assert conv.ask("q1") is False                       # 防抖：忽略
    assert conv.ask("q2") is False
    assert len(conv.history) == 1                        # 未追加

    gate.open(); wait_done(done)
    assert answers == ["ok"]


def test_ask_blank_ignored():
    def chat(history, system_prompt=None):
        return "ok"

    conv, answers, errors, done = make_conv(chat)
    assert conv.ask("   ") is False
    assert conv.ask("") is False
    assert conv.history == []
    assert conv.busy is False                             # 未发起请求


def test_ask_appends_user_and_answers():
    def chat(history, system_prompt=None):
        return "answer"

    conv, answers, errors, done = make_conv(chat)
    assert conv.ask("why?") is True
    wait_done(done)

    assert answers == ["answer"]
    assert conv.history[0] == {"role": "user", "content": "why?"}


def test_error_routes_to_on_error_and_unbusy():
    def chat(history, system_prompt=None):
        raise RuntimeError("boom")

    conv, answers, errors, done = make_conv(chat)
    conv.start("X")
    wait_done(done)

    assert answers == []
    assert isinstance(errors[0], RuntimeError)
    assert conv.busy is False


def test_latest_role_and_append_assistant():
    def chat(history, system_prompt=None):
        return "."

    conv, answers, errors, done = make_conv(chat)
    assert conv.latest_role() is None                    # 空对话
    conv.append_assistant("hi")
    assert conv.latest_role() == "assistant"
    conv.ask("q")
    wait_done(done)
    assert conv.latest_role() == "user"                  # 追问后最新为用户