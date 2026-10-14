"""统一日志初始化（P2-7）。

替代散落的 print，提供带级别的统一日志。调用方通过 get_logger(name)
获取 logger；应用入口（dictionary_gui.main）调用 setup() 配置一次。
消息内容保留原有的 emoji 前缀（如 🔊），仅把「级别/目标」归一。
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """获取命名空间的 logger（各模块用 ``__name__`` 即可）。"""
    return logging.getLogger(name)


def setup(level: int = logging.INFO) -> None:
    """配置全局日志输出到 stderr，含时间戳与级别。"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,
    )