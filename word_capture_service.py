#!/usr/bin/env python3
import subprocess
import time
import threading
import os
import sys
import signal
import re
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


def get_selected_text(service_instance=None):
    """获取选中文本（优化版，检测用户操作）"""
    current_time = time.time()
    
    # 如果是服务实例调用，检查用户操作时间
    if service_instance and current_time - service_instance._user_copy_time < 0.5:
        # 用户最近有复制操作，跳过自动检测
        return None
    
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
                    
                    # 如果是服务实例调用，记录用户操作时间
                    if service_instance and selection == "clipboard":
                        service_instance._user_copy_time = current_time
                        
                    return text
        except Exception as e:
            logger.debug(f"获取选中文本失败 ({selection}): {e}")
    return None


def get_selected_text_primary():
    """安全获取PRIMARY选择（鼠标选中文本），不干扰剪贴板"""
    try:
        # 使用xclip获取PRIMARY选择
        result = subprocess.run(
            ["xclip", "-selection", "primary", "-o"],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            text = result.stdout.strip()
            if text and len(text) < 100:  # 合理的文本长度
                # 验证文本安全性
                if any(ord(c) < 32 for c in text):  # 控制字符检查
                    return None
                if any(char in text for char in ';|`$\\'):  # 安全性检查
                    logger.debug("跳过可能不安全的文本")
                    return None
                if not re.match(r'^[\w\s\-\.\,!?;:"\'()]+$', text):
                    return None
                return text
    except Exception as e:
        logger.debug(f"获取PRIMARY选择失败: {e}")
    
    return None


def get_word_at_position(x, y):
    """获取鼠标位置的单词（安全版，使用PRIMARY选择）"""
    # 首先尝试直接获取PRIMARY选择（不干扰剪贴板）
    selected_text = get_selected_text_primary()
    if selected_text:
        logger.debug(f"通过PRIMARY选择获取文本: '{selected_text}'")
        return selected_text
    
    # 如果PRIMARY选择为空，使用备用方案（尽量避免使用Ctrl+C）
    logger.debug("PRIMARY选择为空，使用备用方案")
    current_clipboard = ""
    should_restore_clipboard = True
    
    try:
        # 先保存当前剪贴板内容
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=1
            )
            if result.returncode == 0:
                current_clipboard = result.stdout
        except Exception as e:
            logger.debug(f"保存剪贴板失败: {e}")

        # 模拟鼠标双击选中单词（比单击更可靠）
        subprocess.run(
            ["xdotool", "mousemove", str(x), str(y), "click", "--repeat", "2", "1"],
            capture_output=True, text=True, timeout=1
        )
        time.sleep(0.1)  # 等待选中生效
        
        # 现在尝试获取PRIMARY选择（双击后应该有选中文本）
        selected_text = get_selected_text_primary()
        if selected_text:
            logger.debug(f"双击后通过PRIMARY选择获取文本: '{selected_text}'")
            should_restore_clipboard = False
            return selected_text
        
        # 如果PRIMARY选择仍然为空，才使用Ctrl+C（最后手段）
        logger.debug("PRIMARY选择仍然为空，使用Ctrl+C备用方案")
        subprocess.run(
            ["xdotool", "key", "ctrl+c"],
            capture_output=True, text=True, timeout=1
        )
        time.sleep(0.1)
        
        # 获取剪贴板内容
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, text=True, timeout=1
        )
        
        if result.returncode == 0:
            text = result.stdout.strip()
            # 验证文本有效性
            if not text or len(text) > 50:
                return None
            if any(ord(c) < 32 for c in text):
                return None
            if any(char in text for char in ';|`$\\'):
                logger.debug("跳过可能不安全的文本")
                return None
            if not re.match(r'^[\w\s\-\.\,!?;:"\'()]+$', text):
                return None
            
            should_restore_clipboard = False
            return text
    except Exception as e:
        logger.debug(f"获取鼠标位置单词失败: {e}")
    finally:
        # 只有在使用Ctrl+C时才需要恢复剪贴板
        if should_restore_clipboard and current_clipboard:
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard", "-i"],
                    input=current_clipboard, text=True, timeout=1
                )
                logger.debug("恢复剪贴板内容")
            except Exception as e:
                logger.debug(f"恢复剪贴板失败: {e}")
    
    return None


class WordCaptureService:
    def __init__(self, poll_interval=0.5, mouse_check_interval=5, enable_mouse_hover=True):
        self.running = False
        self.stopping = False
        self.last_word = ""
        self.last_captured_word = ""
        self.last_mouse_pos = None
        self.callback = None
        self.poll_interval = poll_interval
        self.mouse_check_interval = mouse_check_interval
        self.enable_mouse_hover = enable_mouse_hover  # 是否启用鼠标悬停取词
        self._mouse_stationary_count = 0
        self._user_copy_time = 0  # 记录用户复制操作的时间
        self._last_clipboard_check = 0  # 上次检查剪贴板的时间

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

    def _clean_word(self, text):
        """清理单词前后的标点符号"""
        if not text:
            return text
            
        # 中英文标点符号
        punctuation_chars = '.,!?;:"\'`，。！？；："\'（）【】《》<>[]{}()'
        
        # 清理开头的标点符号
        while text and text[0] in punctuation_chars:
            text = text[1:]
        
        # 清理结尾的标点符号
        while text and text[-1] in punctuation_chars:
            text = text[:-1]
        
        return text.strip()
    
    def set_callback(self, callback):
        self.callback = callback

    def _monitor_loop(self):
        """优化的监控循环，减少抖动和冲突"""
        last_trigger_time = 0
        trigger_cooldown = 0.3  # 300ms冷却时间
        
        while self.running:
            try:
                if self.stopping:
                    time.sleep(0.1)
                    continue
                
                current_time = time.time()
                
                # 检查冷却时间
                if current_time - last_trigger_time < trigger_cooldown:
                    time.sleep(self.poll_interval)
                    continue
                
                # 优先检查选中文本（用户主动操作）
                selected = get_selected_text(self)
                if selected and selected != self.last_word and not self.stopping:
                    # 更严格的重复检测：清理标点后比较
                    cleaned_selected = self._clean_word(selected)
                    cleaned_last = self._clean_word(self.last_captured_word)
                    if cleaned_selected and cleaned_selected == cleaned_last:
                        time.sleep(self.poll_interval)
                        continue
                    
                    # 更新状态并触发回调
                    self.last_word = selected
                    self.last_captured_word = selected
                    last_trigger_time = current_time
                    logger.debug(f"选中文本触发回调: '{selected}'")
                    
                    if self.callback:
                        try:
                            # 获取鼠标位置并传递给回调
                            mouse_info = get_word_under_mouse()
                            if mouse_info:
                                mouse_x, mouse_y, _ = mouse_info
                                # 尝试调用带位置参数的回调
                                try:
                                    self.callback(selected, mouse_x, mouse_y)
                                except TypeError:
                                    # 如果参数不匹配，回退到单参数调用
                                    self.callback(selected)
                            else:
                                self.callback(selected)
                        except Exception as e:
                            logger.error(f"回调执行失败: {e}")
                    else:
                        self._default_handler(selected)
                    
                    # 处理选中文本后跳过鼠标悬停检查，避免冲突
                    time.sleep(self.poll_interval)
                    continue
                
                # 检查鼠标位置变化（被动取词）- 仅在启用时执行
                if self.enable_mouse_hover:
                    mouse_info = get_word_under_mouse()
                    if mouse_info:
                        x, y, window_name = mouse_info
                        
                        # 检查鼠标是否静止
                        if self.last_mouse_pos and self.last_mouse_pos == (x, y):
                            self._mouse_stationary_count += 1
                        else:
                            self._mouse_stationary_count = 0
                        
                        self.last_mouse_pos = (x, y)
                        
                        # 如果鼠标静止时间超过阈值，尝试获取单词
                        if self._mouse_stationary_count >= self.mouse_check_interval:
                            # 使用安全的PRIMARY选择获取单词
                            selected = get_word_at_position(x, y)
                            
                            if selected and selected != self.last_word and not self.stopping:
                                # 清理标点后比较
                                cleaned_selected = self._clean_word(selected)
                                cleaned_last = self._clean_word(self.last_captured_word)
                                if cleaned_selected and cleaned_selected == cleaned_last:
                                    time.sleep(self.poll_interval)
                                    continue
                                
                                # 更新状态并触发回调
                                self.last_word = selected
                                self.last_captured_word = selected
                                last_trigger_time = current_time
                                logger.debug(f"鼠标悬停触发回调: '{selected}'")
                                
                                if self.callback:
                                    try:
                                        self.callback(selected, x, y)
                                    except TypeError:
                                        self.callback(selected)
                                else:
                                    self._default_handler(selected)
                
                time.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                time.sleep(self.poll_interval)

    def _default_handler(self, word):
        """默认处理函数"""
        logger.info(f"捕获到单词: {word}")
        
        # 保存到缓存文件
        try:
            with open(LAST_WORD_FILE, 'w') as f:
                f.write(word)
        except Exception as e:
            logger.error(f"保存单词到缓存文件失败: {e}")


def main():
    """主函数"""
    service = WordCaptureService()
    
    def signal_handler(signum, frame):
        logger.info("收到信号，停止服务")
        service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        service.start()
        logger.info("服务已启动，按Ctrl+C停止")
        
        # 保持主线程运行
        while service.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("用户中断，停止服务")
        service.stop()
    except Exception as e:
        logger.error(f"服务异常: {e}")
        service.stop()


# 为dictionary_gui.py提供的接口函数
_service_instance = None


def get_service():
    """获取服务实例（单例模式）"""
    global _service_instance
    if _service_instance is None:
        _service_instance = WordCaptureService()
    return _service_instance


def start_service(enable_mouse_hover=True):
    """启动取词服务"""
    service = get_service()
    service.enable_mouse_hover = enable_mouse_hover
    service.start()


def stop_service():
    """停止取词服务"""
    global _service_instance
    if _service_instance:
        _service_instance.stop()
        _service_instance = None


def on_capture(callback):
    """设置单词捕获回调函数"""
    service = get_service()
    service.set_callback(callback)


if __name__ == "__main__":
    main()