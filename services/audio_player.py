"""音频播放模块（P2-1）。

将 `dictionary_gui.py` 中的 `play_audio` 及其备用播放逻辑独立成模块，
UI 层只依赖 `play_audio(url)` 一个接口。使用 ffplay 统一处理网络/本地音频。
"""

import os
import tempfile
import threading
import subprocess
import requests
from services.logger import get_logger

logger = get_logger(__name__)


def play_audio(url: str):
    """播放音频文件，使用ffplay统一处理所有格式"""
    if not url:
        logger.warning("🔊 音频URL为空，无法播放")
        return

    # 记录音频URL，方便调试
    logger.info(f"🔊 播放音频请求 - URL: {url}")
    logger.debug(f"🔊 音频URL类型: {'网络URL' if url.startswith('http') else '本地文件'}")

    # 如果是网络URL，检查URL格式
    if url.startswith('http'):
        logger.debug(f"🔊 网络音频URL格式检查: {'有效' if '://' in url else '可能无效'}")
        if len(url) > 200:
            logger.debug(f"🔊 URL过长，截断显示: {url[:200]}...")
        else:
            logger.debug(f"🔊 完整URL: {url}")

    def _play():
        try:
            # 检查ffplay是否可用
            result = subprocess.run(['which', 'ffplay'], capture_output=True)
            if result.returncode != 0:
                logger.warning("🔊 音频播放器 ffplay 未安装，请运行: sudo apt install ffmpeg")
                return

            # 使用ffplay直接播放网络音频（无需下载）
            # -autoexit: 播放完成后自动退出
            # -nodisp: 不显示视频窗口
            # -loglevel quiet: 静默模式，不输出日志
            logger.info("🔊 开始使用ffplay播放网络音频...")
            result = subprocess.run([
                'ffplay',
                '-autoexit',
                '-nodisp',
                '-loglevel', 'quiet',
                url
            ], capture_output=True, timeout=30)

            if result.returncode != 0:
                logger.warning(f"🔊 音频播放失败，返回码: {result.returncode}")
                if result.stderr:
                    error_msg = result.stderr.decode('utf-8', errors='ignore')
                    logger.warning(f"🔊 错误信息: {error_msg}")

                    # 分析常见错误
                    if "Connection refused" in error_msg:
                        logger.warning("🔊 错误类型: 连接被拒绝 - 网络问题或服务器不可用")
                    elif "404" in error_msg:
                        logger.warning("🔊 错误类型: 404 Not Found - 音频文件不存在")
                    elif "403" in error_msg:
                        logger.warning("🔊 错误类型: 403 Forbidden - 访问被拒绝")
                    elif "timed out" in error_msg.lower():
                        logger.warning("🔊 错误类型: 连接超时 - 网络延迟或服务器响应慢")
                    elif "no such file" in error_msg.lower():
                        logger.warning("🔊 错误类型: 文件不存在 - URL可能无效")
                    else:
                        logger.warning("🔊 错误类型: 未知错误")

                # 如果ffplay失败，回退到下载+播放的方式
                logger.info("🔊 尝试使用备用播放方式...")
                _play_fallback(url)
            else:
                logger.info("🔊 音频播放完成")

        except subprocess.TimeoutExpired:
            logger.warning("🔊 音频播放超时 - ffplay进程运行超过30秒")
            logger.warning(f"🔊 超时URL: {url}")
        except Exception as e:
            logger.error(f"🔊 播放音频失败: {e}")
            logger.error(f"🔊 失败URL: {url}")
            import traceback
            logger.debug(f"🔊 详细错误信息: {traceback.format_exc()}")

    def _play_fallback(fallback_url: str):
        """备用播放方式：下载后播放"""
        logger.info(f"🔊 开始备用播放方式 - URL: {fallback_url}")
        try:
            # 下载音频文件
            logger.info("🔊 开始下载音频文件...")
            response = requests.get(fallback_url, timeout=10)
            response.raise_for_status()
            logger.info(f"🔊 下载成功，文件大小: {len(response.content)} bytes")

            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.audio', delete=False, delete_on_close=False) as f:
                f.write(response.content)
                temp_path = f.name
            logger.debug(f"🔊 临时文件创建成功: {temp_path}")

            # 使用ffplay播放本地文件
            logger.info("🔊 开始播放本地音频文件...")
            result = subprocess.run([
                'ffplay',
                '-autoexit',
                '-nodisp',
                '-loglevel', 'quiet',
                temp_path
            ], capture_output=True, timeout=30)

            # 清理临时文件
            try:
                os.unlink(temp_path)
                logger.debug("🔊 临时文件已清理")
            except Exception as e:
                logger.warning(f"🔊 清理临时文件失败: {e}")

            if result.returncode != 0:
                logger.warning(f"🔊 备用播放方式失败，返回码: {result.returncode}")
                if result.stderr:
                    error_msg = result.stderr.decode('utf-8', errors='ignore')
                    logger.warning(f"🔊 备用播放错误信息: {error_msg}")
            else:
                logger.info("🔊 备用播放方式成功")

        except requests.exceptions.RequestException as e:
            logger.error(f"🔊 下载音频文件失败: {e}")
            logger.error(f"🔊 下载失败URL: {fallback_url}")
        except Exception as e:
            logger.error(f"🔊 备用播放方式失败: {e}")

    # 在新线程中播放音频，避免阻塞UI
    threading.Thread(target=_play, daemon=True).start()