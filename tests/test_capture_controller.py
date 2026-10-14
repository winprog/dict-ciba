"""CaptureController 的单元测试。

monkeypatch 替换模块级 start_service/stop_service/on_capture（不触碰真实
取词服务），验证生命周期状态机与 status_text 文案。
"""
import capture_controller as cc
from capture_controller import CaptureController


def _make(monkeypatch, calls, registered=None):
    def fake_on_capture(fn):
        registered.append(fn)

    def fake_start_service(**kw):
        calls.append(("start", kw))

    def fake_stop_service():
        calls.append(("stop",))

    monkeypatch.setattr(cc, "on_capture", fake_on_capture)
    monkeypatch.setattr(cc, "start_service", fake_start_service)
    monkeypatch.setattr(cc, "stop_service", fake_stop_service)


def test_initial_state_and_status(monkeypatch):
    calls, registered = [], []
    _make(monkeypatch, calls, registered)
    c = CaptureController(lambda w: None)
    assert c.running is False
    assert c.hover_enabled is False
    assert c.status_text == "关闭"


def test_constructor_registers_capture_callback(monkeypatch):
    calls, registered = [], []
    _make(monkeypatch, calls, registered)
    cb = lambda w: None
    CaptureController(cb)
    assert len(registered) == 1
    assert registered[0] is cb


def test_start_sets_running_and_calls_service(monkeypatch):
    calls, registered = [], []
    _make(monkeypatch, calls, registered)
    c = CaptureController(lambda w: None)
    c.start()
    assert c.running is True
    assert calls == [("start", {"enable_mouse_hover": False})]


def test_start_passes_hover(monkeypatch):
    calls, registered = [], []
    _make(monkeypatch, calls, registered)
    c = CaptureController(lambda w: None)
    c.hover_enabled = True
    c.start()
    assert calls == [("start", {"enable_mouse_hover": True})]


def test_stop_clears_running(monkeypatch):
    calls, registered = [], []
    _make(monkeypatch, calls, registered)
    c = CaptureController(lambda w: None)
    c.running = True
    c.stop()
    assert c.running is False
    assert calls == [("stop",)]


def test_status_text_variants(monkeypatch):
    calls, registered = [], []
    _make(monkeypatch, calls, registered)
    c = CaptureController(lambda w: None)
    c.running = True
    assert c.status_text == "运行中(仅选中取词)"
    c.hover_enabled = True
    assert c.status_text == "运行中"


def test_apply_hover_noop_when_not_running(monkeypatch):
    calls, registered = [], []
    _make(monkeypatch, calls, registered)
    c = CaptureController(lambda w: None)
    c.apply_hover()
    assert calls == []                     # 未运行不重启


def test_apply_hover_restarts_when_running(monkeypatch):
    calls, registered = [], []
    _make(monkeypatch, calls, registered)
    c = CaptureController(lambda w: None)
    c.running = True
    c.apply_hover()
    assert calls == [("stop",), ("start", {"enable_mouse_hover": False})]