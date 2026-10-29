"""取词服务生命周期（stop→start）回调保持的回归测试。

症状：取词模式开关几次后，点启动状态虽变绿，但捕获词不再回传 GUI。
根因：通过 stop_service 停止后，单例被置 None 丢弃；
再次 start_service 重建了一个没有回调的新实例，capture 回调丢失。
"""
from services.word_capture_service import (
    get_service,
    on_capture,
    stop_service,
)


def test_callback_survives_stop_start_cycle():
    """停止后再启动，capture 回调必须仍在当前服务实例上。"""
    cb = lambda word: None
    on_capture(cb)
    first = get_service()
    assert first.callback is cb  # 首次启动前已绑定

    stop_service()               # 停止并重建
    restarted = get_service()
    assert restarted is first or restarted.callback is cb