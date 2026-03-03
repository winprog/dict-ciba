#!/usr/bin/env python3
import subprocess
import time
import threading
import os
import sys
import signal
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(Path.home() / ".cache" / "word-capture" / "service.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".cache" / "word-capture"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LAST_WORD_FILE = CACHE_DIR / "last_word.txt"
PID_FILE = CACHE_DIR / "service.pid"


def check_dependencies():
    """检查依赖工具是否安装"""
    dependencies = ["xdotool", "xclip"]
    missing = []
    for dep in dependencies:
        try:
            subprocess.run([dep, "--version"], capture_output=True, timeout=1)
        except (subprocess.SubprocessError, FileNotFoundError):
            missing.append(dep)
    if missing:
        logger.error(f"缺少依赖工具: {', '.join(missing)}")
        logger.error("请安装这些工具: sudo apt install xdotool xclip")
        return False
    return True


def get_word_under_mouse():
    """获取鼠标位置和窗口信息"""
    window_name = ""
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True, text=True, timeout=1
        )
        window_name = result.stdout.strip() if result.returncode == 0 else ""
    except Exception as e:
        logger.debug(f"获取窗口名称失败: {e}")

    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation", "--shell"],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            x = y = None
            for line in lines:
                if line.startswith('X='):
                    x = int(line.split('=')[1])
                elif line.startswith('Y='):
                    y = int(line.split('=')[1])
            if x is not None and y is not None:
                return x, y, window_name
    except Exception as e:
        logger.debug(f"获取鼠标位置失败: {e}")
    
    return None


def get_selected_text():
    """获取选中文本"""
    for selection in ["primary", "clipboard"]:
        try:
            result = subprocess.run(
                ["xclip", "-selection", selection, "-o"],
                capture_output=True, text=True, timeout=1
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                if text and len(text) < 100 and not text.startswith('file://'):
                    if any(ord(c) < 32 for c in text):
                        logger.debug("跳过包含控制字符的文本")
                        continue
                    # 验证文本安全性
                    if any(char in text for char in ';|`$\\'):
                        logger.debug("跳过可能不安全的文本")
                        continue
                    return text
        except Exception as e:
            logger.debug(f"获取选中文本失败 ({selection}): {e}")
    return None


def get_word_at_position(x, y):
    """获取鼠标位置的单词"""
    try:
        # 先保存当前剪贴板内容
        current_clipboard = ""
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=1
            )
            if result.returncode == 0:
                current_clipboard = result.stdout
        except Exception as e:
            logger.debug(f"保存剪贴板失败: {e}")

        # 模拟 Ctrl+C 复制
        result = subprocess.run(
            ["xdotool", "key", "ctrl+c"],
            capture_output=True, text=True, timeout=1
        )
        time.sleep(0.05)
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            text = result.stdout.strip()
            if text and any(ord(c) < 32 for c in text):
                return None
            # 验证文本安全性
            if any(char in text for char in ';|`$\\'):
                logger.debug("跳过可能不安全的文本")
                return None
            return text
    except Exception as e:
        logger.debug(f"获取鼠标位置单词失败: {e}")
    finally:
        # 恢复剪贴板内容
        try:
            if current_clipboard:
                subprocess.run(
                    ["xclip", "-selection", "clipboard", "-i"],
                    input=current_clipboard, text=True, timeout=1
                )
        except Exception as e:
            logger.debug(f"恢复剪贴板失败: {e}")
    
    return None


class WordCaptureService:
    def __init__(self, poll_interval=0.5, mouse_check_interval=5):
        self.running = False
        self.stopping = False
        self.last_word = ""
        self.last_captured_word = ""
        self.last_mouse_pos = None
        self.callback = None
        self.poll_interval = poll_interval
        self.mouse_check_interval = mouse_check_interval
        self._mouse_stationary_count = 0

    def start(self):
        if self.running:
            logger.info("服务已经在运行")
            return
        
        if not check_dependencies():
            logger.error("依赖检查失败，服务启动失败")
            return
        
        self.stopping = False
        
        try:
            with open(PID_FILE, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            logger.error(f"创建PID文件失败: {e}")
            return
        
        self.running = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        logger.info(f"单词捕获服务已启动 (PID: {os.getpid()})")

    def stop(self):
        self.running = False
        self.stopping = True
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except Exception as e:
            logger.error(f"删除PID文件失败: {e}")
        logger.info("单词捕获服务已停止")

    def set_callback(self, callback):
        self.callback = callback

    def _monitor_loop(self):
        while self.running:
            try:
                if self.stopping:
                    time.sleep(0.1)
                    continue
                    
                result = subprocess.run(
                    ["xdotool", "getmouselocation", "--shell"],
                    capture_output=True, text=True, timeout=1
                )
                current_pos = None
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    x = y = None
                    for line in lines:
                        if line.startswith('X='):
                            x = int(line.split('=')[1])
                        elif line.startswith('Y='):
                            y = int(line.split('=')[1])
                    if x is not None and y is not None:
                        current_pos = (x, y)
                
                if current_pos is not None and current_pos == self.last_mouse_pos:
                    self._mouse_stationary_count += 1
                else:
                    self._mouse_stationary_count = 0
                    if current_pos is not None:
                        self.last_mouse_pos = current_pos
                
                if self._mouse_stationary_count >= self.mouse_check_interval:
                    # 重置计数但设置一个冷却期
                    self._mouse_stationary_count = -5  # 5秒冷却期
                    selected = get_word_at_position(*self.last_mouse_pos) if self.last_mouse_pos else None
                    if selected and selected != self.last_word and not self.stopping:
                        if self.last_captured_word == selected:
                            continue
                        self.last_word = selected
                        self.last_captured_word = selected
                        logger.debug(f"触发回调: '{selected}'")
                        if self.callback:
                            try:
                                self.callback(selected)
                            except Exception as e:
                                logger.error(f"回调执行失败: {e}")
                        else:
                            self._default_handler(selected)
                
                selected = get_selected_text()
                if selected and selected != self.last_word and not self.stopping:
                    if self.last_captured_word == selected:
                        continue
                    self.last_word = selected
                    self.last_captured_word = selected
                    logger.debug(f"触发回调: '{selected}'")
                    if self.callback:
                        try:
                            self.callback(selected)
                        except Exception as e:
                            logger.error(f"回调执行失败: {e}")
                    else:
                        self._default_handler(selected)
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
            
            time.sleep(self.poll_interval)
        logger.info("单词捕获服务停止监控")

    def _default_handler(self, word):
        if not self.stopping:
            logger.info(f"捕获到: {word}")


_service = None


def get_service():
    global _service
    if _service is None:
        _service = WordCaptureService()
    return _service


def start_service():
    get_service().start()


def stop_service():
    get_service().stop()

def on_capture(callback):
    get_service().set_callback(callback)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Word capture service for Ubuntu")
    parser.add_argument("command", choices=["start", "stop", "status"], 
                       help="Command to execute")
    parser.add_argument("--poll-interval", type=float, default=0.5, 
                       help="Polling interval in seconds (default: 0.5)")
    parser.add_argument("--mouse-check-interval", type=int, default=5, 
                       help="Mouse stationary check interval (default: 5)")
    args = parser.parse_args()
    
    if args.command == "start":
        # 使用命令行参数初始化服务
        _service = WordCaptureService(
            poll_interval=args.poll_interval,
            mouse_check_interval=args.mouse_check_interval
        )
        start_service()
        while get_service().running:
            time.sleep(0.1)
    elif args.command == "stop":
        if PID_FILE.exists():
            try:
                with open(PID_FILE) as f:
                    pid = int(f.read())
                try:
                    os.kill(pid, signal.SIGTERM)
                    logger.info(f"发送停止信号到 {pid}")
                except Exception as e:
                    logger.error(f"进程未找到: {e}")
                try:
                    PID_FILE.unlink()
                except Exception as e:
                    logger.error(f"删除PID文件失败: {e}")
            except Exception as e:
                logger.error(f"停止服务失败: {e}")
        else:
            logger.info("服务未运行")
    elif args.command == "status":
        if PID_FILE.exists():
            try:
                with open(PID_FILE) as f:
                    pid = int(f.read())
                try:
                    os.kill(pid, 0)
                    logger.info(f"服务正在运行 (PID: {pid})")
                except Exception as e:
                    logger.info("服务未运行 (PID文件过时)")
                    try:
                        PID_FILE.unlink()
                    except Exception as e:
                        logger.error(f"删除过时PID文件失败: {e}")
            except Exception as e:
                logger.error(f"检查服务状态失败: {e}")
        else:
            logger.info("服务未运行")