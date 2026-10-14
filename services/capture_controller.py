"""取词模式控制（P2-2）。

封装取词服务（word_capture_service）的启停与悬停设置，把「服务生命周期 + 状态」
从 UI 解耦出来。UI 只需：
- 设置 `hover_enabled`
- 调用 `start()` / `stop()` / `apply_hover()`
- 订阅捕获回调（构造时传入）

捕获到词后的窗口联动与查询由回调（on_captured_word）交给 UI 编排。
"""

import time
from services.word_capture_service import start_service, stop_service, on_capture


class CaptureController:
    """取词模式生命周期控制。"""

    def __init__(self, on_captured_word):
        self._on_captured_word = on_captured_word
        self.running = False
        self.hover_enabled = False
        # 捕获到词后由服务回调转发给 UI
        on_capture(self._on_captured_word)

    @property
    def status_text(self):
        """供 UI 展示的状态文案。"""
        if not self.running:
            return "关闭"
        return "运行中" if self.hover_enabled else "运行中(仅选中取词)"

    def start(self):
        """启动取词服务（含悬停设置）。失败抛出异常由 UI 提示。"""
        start_service(enable_mouse_hover=self.hover_enabled)
        self.running = True

    def stop(self):
        """停止取词服务。"""
        stop_service()
        self.running = False

    def apply_hover(self):
        """悬停设置变化后重启服务以生效（仅在运行时需要）。"""
        if not self.running:
            return
        self.stop()
        time.sleep(0.1)  # 短暂等待确保服务完全停止
        self.start()