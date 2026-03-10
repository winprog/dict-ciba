import json
import re
import requests
import tempfile
import subprocess
import threading
import sys
import os
import time
from typing import Optional, Dict, Any
from tkinter import *
from tkinter import messagebox

# 导入取词服务
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from word_capture_service import get_service, start_service, stop_service, on_capture
from word_state_manager import WordStateManager
from iciba import query_word


def play_audio(url: str):
    """播放音频文件，使用ffplay统一处理所有格式"""
    if not url:
        print("音频URL为空，无法播放")
        return
    
    # 记录音频URL，方便调试
    print(f"🔊 播放音频请求 - URL: {url}")
    print(f"🔊 音频URL类型: {'网络URL' if url.startswith('http') else '本地文件'}")
    
    # 如果是网络URL，检查URL格式
    if url.startswith('http'):
        print(f"🔊 网络音频URL格式检查: {'有效' if '://' in url else '可能无效'}")
        if len(url) > 200:
            print(f"🔊 URL过长，截断显示: {url[:200]}...")
        else:
            print(f"🔊 完整URL: {url}")
    
    def _play():
        try:
            # 检查ffplay是否可用
            result = subprocess.run(['which', 'ffplay'], capture_output=True)
            if result.returncode != 0:
                print("音频播放器 ffplay 未安装，请运行: sudo apt install ffmpeg")
                return
            
            # 使用ffplay直接播放网络音频（无需下载）
            # -autoexit: 播放完成后自动退出
            # -nodisp: 不显示视频窗口
            # -loglevel quiet: 静默模式，不输出日志
            print("🔊 开始使用ffplay播放网络音频...")
            result = subprocess.run([
                'ffplay', 
                '-autoexit', 
                '-nodisp', 
                '-loglevel', 'quiet',
                url
            ], capture_output=True, timeout=30)
            
            if result.returncode != 0:
                print(f"🔊 音频播放失败，返回码: {result.returncode}")
                if result.stderr:
                    error_msg = result.stderr.decode('utf-8', errors='ignore')
                    print(f"🔊 错误信息: {error_msg}")
                    
                    # 分析常见错误
                    if "Connection refused" in error_msg:
                        print("🔊 错误类型: 连接被拒绝 - 网络问题或服务器不可用")
                    elif "404" in error_msg:
                        print("🔊 错误类型: 404 Not Found - 音频文件不存在")
                    elif "403" in error_msg:
                        print("🔊 错误类型: 403 Forbidden - 访问被拒绝")
                    elif "timed out" in error_msg.lower():
                        print("🔊 错误类型: 连接超时 - 网络延迟或服务器响应慢")
                    elif "no such file" in error_msg.lower():
                        print("🔊 错误类型: 文件不存在 - URL可能无效")
                    else:
                        print("🔊 错误类型: 未知错误")
                
                # 如果ffplay失败，回退到下载+播放的方式
                print("🔊 尝试使用备用播放方式...")
                _play_fallback(url)
            else:
                print("🔊 音频播放完成")
                
        except subprocess.TimeoutExpired:
            print("🔊 音频播放超时 - ffplay进程运行超过30秒")
            print(f"🔊 超时URL: {url}")
        except Exception as e:
            print(f"🔊 播放音频失败: {e}")
            print(f"🔊 失败URL: {url}")
            import traceback
            print(f"🔊 详细错误信息: {traceback.format_exc()}")
    
    def _play_fallback(fallback_url: str):
        """备用播放方式：下载后播放"""
        print(f"🔊 开始备用播放方式 - URL: {fallback_url}")
        try:
            # 下载音频文件
            print("🔊 开始下载音频文件...")
            response = requests.get(fallback_url, timeout=10)
            response.raise_for_status()
            print(f"🔊 下载成功，文件大小: {len(response.content)} bytes")
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.audio', delete=False, delete_on_close=False) as f:
                f.write(response.content)
                temp_path = f.name
            print(f"🔊 临时文件创建成功: {temp_path}")
            
            # 使用ffplay播放本地文件
            print("🔊 开始播放本地音频文件...")
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
                print("🔊 临时文件已清理")
            except Exception as e:
                print(f"🔊 清理临时文件失败: {e}")
                
            if result.returncode != 0:
                print(f"🔊 备用播放方式失败，返回码: {result.returncode}")
                if result.stderr:
                    error_msg = result.stderr.decode('utf-8', errors='ignore')
                    print(f"🔊 备用播放错误信息: {error_msg}")
            else:
                print("🔊 备用播放方式成功")
                
        except requests.exceptions.RequestException as e:
            print(f"🔊 下载音频文件失败: {e}")
            print(f"🔊 下载失败URL: {fallback_url}")
        except Exception as e:
            print(f"🔊 备用播放方式失败: {e}")
    
    # 在新线程中播放音频，避免阻塞UI
    threading.Thread(target=_play, daemon=True).start()


class DictionaryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dictionary")
        
        # 获取屏幕尺寸
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # 计算窗口初始位置（屏幕右下角）
        window_width = 500
        window_height = 400
        x = screen_width - window_width - 50  # 距离右边50像素
        y = screen_height - window_height - 50  # 距离底部50像素
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 窗口管理状态
        self.capture_mode = False
        self.window_visible = True
        self.auto_hide_timer = None
        self.original_geometry = None
        self.last_mouse_position = None  # 记录最后一次取词位置
        
        # 单词状态管理器
        self.word_state_manager = WordStateManager()
        
        # 设置窗口初始属性
        self.root.attributes('-topmost', False)  # 初始不在最上层
        self.root.attributes('-alpha', 0.95)     # 设置透明度
        
        # 绑定窗口焦点事件
        self.root.bind('<FocusIn>', self.on_focus_in)
        self.root.bind('<FocusOut>', self.on_focus_out)
        
        # 顶部按钮区域
        self.top_frame = Frame(root, pady=5)
        self.top_frame.pack(fill=X)
        
        # 取词模式按钮
        self.capture_btn = Button(self.top_frame, text="启动取词模式", 
                                 command=self.toggle_capture_mode,
                                 bg="lightgreen", font=("Arial", 10))
        self.capture_btn.pack(side=LEFT, padx=10)
        
        # 状态标签
        self.status_label = Label(self.top_frame, text="取词模式: 关闭", 
                                 font=("Arial", 10), fg="gray")
        self.status_label.pack(side=LEFT, padx=10)
        
        # 鼠标悬停取词选项
        self.enable_hover_var = BooleanVar(value=False)  # 默认禁用鼠标悬停
        self.hover_check = Checkbutton(self.top_frame, text="启用鼠标悬停取词",
                                       variable=self.enable_hover_var,
                                       font=("Arial", 9),
                                       command=self.toggle_hover_capture)
        self.hover_check.pack(side=LEFT, padx=10)
        
        # 窗口控制按钮
        self.window_btn = Button(self.top_frame, text="置顶显示", 
                                command=self.toggle_window_topmost,
                                bg="lightblue", font=("Arial", 9))
        self.window_btn.pack(side=RIGHT, padx=5)
        
        self.hide_btn = Button(self.top_frame, text="隐藏窗口", 
                               command=self.hide_window,
                               bg="lightyellow", font=("Arial", 9))
        self.hide_btn.pack(side=RIGHT, padx=5)
        
        # 输入区域
        self.input_frame = Frame(root, pady=10)
        self.input_frame.pack(fill=X)
        
        self.entry = Entry(self.input_frame, font=("Arial", 14))
        self.entry.pack(side=LEFT, fill=X, expand=True, padx=(10, 5))
        self.entry.bind("<Return>", lambda e: self.search())
        
        self.btn = Button(self.input_frame, text="Search", command=self.search)
        self.btn.pack(side=RIGHT, padx=(5, 10))
        
        # 结果区域
        self.result_frame = Frame(root, padx=10, pady=10)
        self.result_frame.pack(fill=BOTH, expand=True)
        
        self.canvas = Canvas(self.result_frame)
        self.scrollbar = Scrollbar(self.result_frame, orient=VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # 绑定鼠标滚轮事件到整个窗口，确保一致的滚动行为
        def _on_mousewheel(event):
            """处理鼠标滚轮事件"""
            # 正确的滚轮事件处理逻辑：
            # 向上滚动 (event.delta > 0): 视图向上移动，使用负数
            # 向下滚动 (event.delta < 0): 视图向下移动，使用正数
            delta = -1 * (event.delta // 120)  # 标准化滚轮值
            # 滚动Canvas
            self.canvas.yview_scroll(delta, "units")
            
            # 调试信息
            print(f"🔍 滚轮事件: delta={event.delta}, 滚动量={delta}")
            
            # 返回"break"阻止事件进一步传播
            return "break"
        
        def _on_linux_mousewheel(event):
            """处理Linux鼠标滚轮事件"""
            # Linux系统使用Button-4和Button-5事件
            if event.num == 4:
                # 向上滚动
                self.canvas.yview_scroll(-1, "units")
                print("🔍 Linux滚轮事件: 向上滚动")
            elif event.num == 5:
                # 向下滚动
                self.canvas.yview_scroll(1, "units")
                print("🔍 Linux滚轮事件: 向下滚动")
            
            # 返回"break"阻止事件进一步传播
            return "break"
        
        # 使用bind_all绑定到整个应用程序，确保所有组件都能接收滚轮事件
        self.root.bind_all("<MouseWheel>", _on_mousewheel)
        self.root.bind_all("<Button-4>", _on_linux_mousewheel)  # Linux向上滚动
        self.root.bind_all("<Button-5>", _on_linux_mousewheel)  # Linux向下滚动
        
        # 为Canvas启用焦点，确保能接收滚轮事件
        self.canvas.focus_set()
        
        # 为Canvas绑定滚轮事件，确保能接收事件
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        self.canvas.bind("<Button-4>", _on_linux_mousewheel)
        self.canvas.bind("<Button-5>", _on_linux_mousewheel)
        
        # 为滚动条绑定滚轮事件
        self.scrollbar.bind("<MouseWheel>", _on_mousewheel)
        self.scrollbar.bind("<Button-4>", _on_linux_mousewheel)
        self.scrollbar.bind("<Button-5>", _on_linux_mousewheel)
        
        # 为结果框架绑定滚轮事件
        self.result_frame.bind("<MouseWheel>", _on_mousewheel)
        self.result_frame.bind("<Button-4>", _on_linux_mousewheel)
        self.result_frame.bind("<Button-5>", _on_linux_mousewheel)
        
        # 为可滚动框架绑定滚轮事件
        self.scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
        self.scrollable_frame.bind("<Button-4>", _on_linux_mousewheel)
        self.scrollable_frame.bind("<Button-5>", _on_linux_mousewheel)
        
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        
        self.current_data = None
        
        # 设置取词回调
        on_capture(self.handle_captured_word)
        
        # 窗口关闭时停止取词服务
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def toggle_hover_capture(self):
        """切换鼠标悬停取词设置"""
        if self.capture_mode:
            # 如果取词模式正在运行，需要重启服务以应用新设置
            stop_service()
            time.sleep(0.1)  # 短暂等待确保服务完全停止
            start_service(enable_mouse_hover=self.enable_hover_var.get())
            
            status_text = "运行中" if self.enable_hover_var.get() else "运行中(仅选中取词)"
            self.status_label.config(text=f"取词模式: {status_text}")
    
    def toggle_capture_mode(self):
        """切换取词模式"""
        if not self.capture_mode:
            # 启动取词模式
            try:
                start_service(enable_mouse_hover=self.enable_hover_var.get())
                self.capture_mode = True
                self.capture_btn.config(text="停止取词模式", bg="lightcoral")
                
                status_text = "运行中" if self.enable_hover_var.get() else "运行中(仅选中取词)"
                self.status_label.config(text=f"取词模式: {status_text}", fg="green")
            except Exception as e:
                messagebox.showerror("错误", f"启动取词服务失败: {e}")
        else:
            # 停止取词模式
            stop_service()
            self.capture_mode = False
            self.capture_btn.config(text="启动取词模式", bg="lightgreen")
            self.status_label.config(text="取词模式: 关闭", fg="gray")
    
    def toggle_window_topmost(self):
        """切换窗口置顶状态"""
        current_state = self.root.attributes('-topmost')
        new_state = not current_state
        self.root.attributes('-topmost', new_state)
        
        if new_state:
            self.window_btn.config(text="取消置顶", bg="lightcoral")
        else:
            self.window_btn.config(text="置顶显示", bg="lightblue")
    
    def hide_window(self):
        """隐藏窗口"""
        self.root.withdraw()  # 隐藏窗口
        self.window_visible = False
        self.hide_btn.config(text="显示窗口", bg="lightgreen")
        
        # 取消之前的定时器
        if self.auto_hide_timer:
            self.root.after_cancel(self.auto_hide_timer)
            self.auto_hide_timer = None
    
    def show_window(self):
        """显示窗口"""
        print("🔍 [show_window] 开始显示窗口")
        
        # 记录显示前的窗口状态
        window_id = self.root.winfo_id()
        print(f"🔍 [show_window] 窗口ID: {window_id}")
        print(f"🔍 [show_window] 窗口可见性: {self.window_visible}")
        
        self.root.deiconify()  # 显示窗口
        self.window_visible = True
        self.hide_btn.config(text="隐藏窗口", bg="lightyellow")
        
        # 确保窗口完全显示后再进行桌面移动
        self.root.update_idletasks()
        
        # 记录显示后的窗口状态
        geometry = self.root.geometry()
        print(f"🔍 [show_window] 窗口几何位置: {geometry}")
        
        # 在多桌面环境中，确保窗口显示在当前工作桌面
        print("🔍 [show_window] 调度多桌面检查 (100ms后)")
        self.root.after(100, self._ensure_window_on_current_desktop)  # 延迟100ms确保窗口完全显示
        
        # 取消自动隐藏定时器
        if self.auto_hide_timer:
            self.root.after_cancel(self.auto_hide_timer)
            self.auto_hide_timer = None
        
        print("🔍 [show_window] 显示窗口完成")

    def _ensure_window_on_current_desktop(self):
        """在多桌面环境中确保窗口显示在当前工作桌面"""
        print("🔍 [_ensure_window_on_current_desktop] 开始多桌面检查")
        
        try:
            # 获取窗口ID（确保窗口已完全初始化）
            window_id = self.root.winfo_id()
            print(f"🔍 [_ensure_window_on_current_desktop] 窗口ID: {window_id} (0x{window_id:08x})")
            
            # 检查窗口是否有效（非零ID）
            if window_id == 0:
                print("⚠️ [_ensure_window_on_current_desktop] 窗口ID为0，窗口可能未完全初始化，延迟重试...")
                # 延迟重试
                self.root.after(500, self._ensure_window_on_current_desktop)
                return
            
            # 检查窗口ID是否发生了变化（处理窗口重新映射的情况）
            if hasattr(self, '_last_window_id') and self._last_window_id != window_id:
                print(f"🔄 [_ensure_window_on_current_desktop] 窗口ID发生变化: 旧ID={self._last_window_id}, 新ID={window_id}")
                print("🔍 [_ensure_window_on_current_desktop] 窗口可能被重新映射，更新窗口ID记录")
                
                # 窗口ID发生变化时，重新获取窗口列表并查找正确的窗口ID
                print("🔄 [_ensure_window_on_current_desktop] 重新扫描窗口列表查找正确窗口ID...")
                import subprocess
                result = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    window_lines = result.stdout.strip().split('\n')
                    for wline in window_lines:
                        if 'Dictionary' in wline:  # 查找包含字典标题的窗口
                            try:
                                parts = wline.split()
                                if len(parts) >= 3:
                                    wmctrl_window_id_hex = parts[0]
                                    wmctrl_window_id_int = int(wmctrl_window_id_hex, 16)
                                    # 检查窗口ID是否接近（可能只是变化了1）
                                    if abs(wmctrl_window_id_int - window_id) <= 1:
                                        print(f"🔄 [_ensure_window_on_current_desktop] 找到新窗口ID: {wmctrl_window_id_int} ({wmctrl_window_id_hex})")
                                        window_id = wmctrl_window_id_int
                                        break
                            except (ValueError, IndexError) as e:
                                print(f"⚠️ [_ensure_window_on_current_desktop] 解析窗口行失败: {wline}, 错误: {e}")
            
            # 更新最后记录的窗口ID
            self._last_window_id = window_id
            
            # 记录当前窗口状态
            geometry = self.root.geometry()
            print(f"🔍 [_ensure_window_on_current_desktop] 当前窗口几何位置: {geometry}")
            
            # 获取鼠标位置（用于确定当前桌面）
            mouse_x = None
            mouse_y = None
            if self.last_mouse_position:
                mouse_x, mouse_y = self.last_mouse_position
                print(f"🔍 [_ensure_window_on_current_desktop] 最后取词位置: X={mouse_x}, Y={mouse_y}")
            
            # 获取屏幕信息
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            print(f"🔍 [_ensure_window_on_current_desktop] 屏幕尺寸: {screen_width}x{screen_height}")
            
            # 方法1: 使用系统wmctrl工具获取当前桌面（Linux）
            try:
                import subprocess
                
                # 获取当前桌面信息
                print("🔍 [_ensure_window_on_current_desktop] 获取桌面信息...")
                result = subprocess.run(['wmctrl', '-d'], 
                                      capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    print(f"🔍 [_ensure_window_on_current_desktop] 桌面信息:\n{result.stdout}")
                    lines = result.stdout.strip().split('\n')
                    
                    current_desktop_num = None
                    desktop_count = len(lines)
                    print(f"🔍 [_ensure_window_on_current_desktop] 桌面数量: {desktop_count}")
                    
                    for line in lines:
                        if '*' in line:  # 当前桌面有*标记
                            parts = line.split()
                            current_desktop_num = parts[0]  # 桌面编号
                            
                            print(f"🔍 [_ensure_window_on_current_desktop] 检测到当前桌面: {current_desktop_num}")
                            print(f"🔍 [_ensure_window_on_current_desktop] 桌面详情: {line}")
                            break
                    
                    if current_desktop_num:
                        # 首先检查窗口是否已经在目标桌面
                        print("🔍 [_ensure_window_on_current_desktop] 检查窗口当前桌面...")
                        result = subprocess.run(['wmctrl', '-l'], 
                                              capture_output=True, text=True, timeout=3)
                        if result.returncode == 0:
                            window_lines = result.stdout.strip().split('\n')
                            print(f"🔍 [_ensure_window_on_current_desktop] 窗口列表: {len(window_lines)} 个窗口")
                            
                            window_found = False
                            window_current_desktop = None
                            
                            for wline in window_lines:
                                # 解析wmctrl输出的窗口ID（十六进制字符串转整数）
                                try:
                                    parts = wline.split()
                                    if len(parts) >= 3:
                                        wmctrl_window_id_hex = parts[0]  # 如 "0x01200040"
                                        wmctrl_desktop = parts[1]       # 如 "1"
                                        
                                        # 将十六进制字符串转换为整数进行比较
                                        wmctrl_window_id_int = int(wmctrl_window_id_hex, 16)
                                        
                                        print(f"🔍 [_ensure_window_on_current_desktop] 匹配窗口ID: 期望={window_id}(0x{window_id:08x}), 实际={wmctrl_window_id_int}({wmctrl_window_id_hex}), 桌面={wmctrl_desktop}")
                                        
                                        # 允许窗口ID有小的变化（窗口可能被重新映射）
                                        if wmctrl_window_id_int == window_id or abs(wmctrl_window_id_int - window_id) <= 1:
                                            window_found = True
                                            window_current_desktop = wmctrl_desktop
                                            
                                            # 如果ID有变化，更新为实际的窗口ID
                                            if wmctrl_window_id_int != window_id:
                                                print(f"🔄 [_ensure_window_on_current_desktop] 窗口ID已更新: {window_id} -> {wmctrl_window_id_int}")
                                                window_id = wmctrl_window_id_int
                                            
                                            print(f"🔍 [_ensure_window_on_current_desktop] 找到窗口信息: {wline}")
                                            print(f"🔍 [_ensure_window_on_current_desktop] 窗口当前桌面: {window_current_desktop}")
                                            print(f"🔍 [_ensure_window_on_current_desktop] 目标桌面: {current_desktop_num}")
                                            
                                            if window_current_desktop == current_desktop_num:
                                                print(f"✅ [_ensure_window_on_current_desktop] 窗口已在目标桌面 {current_desktop_num}")
                                                # 只需激活窗口
                                                print("🔍 [_ensure_window_on_current_desktop] 激活窗口...")
                                                subprocess.run(['wmctrl', '-i', '-a', str(window_id)],
                                                             timeout=2)
                                                return
                                            else:
                                                print(f"🔍 [_ensure_window_on_current_desktop] 窗口不在目标桌面，需要移动")
                                                print(f"🔍 [_ensure_window_on_current_desktop] 从桌面 {window_current_desktop} 移动到桌面 {current_desktop_num}")
                                                break
                                except (ValueError, IndexError) as e:
                                    print(f"⚠️ [_ensure_window_on_current_desktop] 解析窗口行失败: {wline}, 错误: {e}")
                                    continue
                            
                            if not window_found:
                                print("⚠️ [_ensure_window_on_current_desktop] 在窗口列表中未找到当前窗口")
                                print(f"🔍 [_ensure_window_on_current_desktop] 查找窗口ID: {window_id}")
                                print(f"🔍 [_ensure_window_on_current_desktop] 窗口列表: {window_lines}")
                            
                            # 将窗口移动到当前桌面
                            if window_current_desktop and window_current_desktop != current_desktop_num:
                                print(f"🔄 [_ensure_window_on_current_desktop] 正在移动窗口到桌面 {current_desktop_num}...")
                                result = subprocess.run(['wmctrl', '-i', '-r', 
                                               str(window_id), '-t', current_desktop_num],
                                              capture_output=True, text=True, timeout=3)
                                
                                print(f"🔍 [_ensure_window_on_current_desktop] 移动命令返回码: {result.returncode}")
                                if result.stdout:
                                    print(f"🔍 [_ensure_window_on_current_desktop] 移动命令输出: {result.stdout}")
                                if result.stderr:
                                    print(f"🔍 [_ensure_window_on_current_desktop] 移动命令错误: {result.stderr}")
                                
                                if result.returncode == 0:
                                    print(f"✅ [_ensure_window_on_current_desktop] 使用wmctrl移动窗口到桌面 {current_desktop_num}")
                                    
                                    # 激活窗口确保显示
                                    print("🔍 [_ensure_window_on_current_desktop] 激活窗口...")
                                    subprocess.run(['wmctrl', '-i', '-a', str(window_id)],
                                                 timeout=2)
                                    
                                    # 强制窗口重绘
                                    print("🔍 [_ensure_window_on_current_desktop] 强制窗口重绘...")
                                    self.root.update_idletasks()
                                    self.root.deiconify()
                                    
                                    # 验证移动结果
                                    print("🔍 [_ensure_window_on_current_desktop] 验证移动结果...")
                                    result = subprocess.run(['wmctrl', '-l'], 
                                                          capture_output=True, text=True, timeout=2)
                                    if result.returncode == 0:
                                        window_lines = result.stdout.strip().split('\n')
                                        for wline in window_lines:
                                            if str(window_id) in wline:
                                                current_desktop = wline.split()[1]
                                                print(f"🔍 [_ensure_window_on_current_desktop] 验证结果: 窗口现在在桌面 {current_desktop}")
                                                break
                                    
                                    return
                                else:
                                    print(f"❌ [_ensure_window_on_current_desktop] wmctrl移动失败")
                            else:
                                print(f"ℹ️ [_ensure_window_on_current_desktop] 窗口已在正确桌面 {current_desktop_num}，无需移动")
                                
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"⚠️ [_ensure_window_on_current_desktop] wmctrl异常: {e}")
                print(f"🔍 [_ensure_window_on_current_desktop] 错误类型: {type(e)}")
                
            # 方法2: 使用xdotool作为备用方案（仅在wmctrl失败时使用）
            try:
                import subprocess
                
                # 只有在wmctrl没有找到窗口时才使用xdotool
                if mouse_x is not None and current_desktop_num is None:
                    print(f"🔍 [_ensure_window_on_current_desktop] 使用xdotool作为备用方案...")
                    print(f"🔍 [_ensure_window_on_current_desktop] 鼠标位置: X={mouse_x}")
                    
                    # 获取屏幕宽度
                    print(f"🔍 [_ensure_window_on_current_desktop] 屏幕宽度: {screen_width}")
                    
                    # 获取桌面数量
                    result = subprocess.run(['xdotool', 'get_num_desktops'], 
                                          capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        num_desktops = int(result.stdout.strip())
                        print(f"🔍 [_ensure_window_on_current_desktop] 桌面数量: {num_desktops}")
                        
                        if num_desktops > 1:
                            # 计算当前桌面（基于鼠标位置）
                            desktop_width = screen_width // num_desktops
                            calculated_desktop = mouse_x // desktop_width
                            
                            # 修正计算：确保桌面编号在有效范围内
                            calculated_desktop = max(0, min(calculated_desktop, num_desktops - 1))
                            
                            print(f"🔍 [_ensure_window_on_current_desktop] 桌面宽度: {desktop_width}")
                            print(f"🔍 [_ensure_window_on_current_desktop] 计算得到的桌面: {calculated_desktop}")
                            
                            # 使用xdotool设置窗口桌面
                            print(f"🔄 [_ensure_window_on_current_desktop] 使用xdotool移动窗口到桌面 {calculated_desktop}")
                            result = subprocess.run(['xdotool', 'set_desktop_for_window', 
                                                       str(window_id), str(calculated_desktop)],
                                                      capture_output=True, text=True, timeout=2)
                            
                            print(f"🔍 [_ensure_window_on_current_desktop] xdotool命令返回码: {result.returncode}")
                            if result.stdout:
                                print(f"🔍 [_ensure_window_on_current_desktop] xdotool输出: {result.stdout}")
                            if result.stderr:
                                print(f"🔍 [_ensure_window_on_current_desktop] xdotool错误: {result.stderr}")
                            
                            if result.returncode == 0:
                                print(f"✅ [_ensure_window_on_current_desktop] 使用xdotool移动窗口到桌面 {calculated_desktop}")
                                
                                # 激活窗口
                                subprocess.run(['xdotool', 'windowactivate', str(window_id)],
                                             timeout=2)
                                
                                return
                            else:
                                print(f"❌ [_ensure_window_on_current_desktop] xdotool移动失败")
                        else:
                            print("ℹ️ [_ensure_window_on_current_desktop] 只有一个桌面，无需移动")
                    else:
                        print(f"❌ [_ensure_window_on_current_desktop] 无法获取桌面数量")
                        
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"⚠️ [_ensure_window_on_current_desktop] xdotool异常: {e}")
                
            print("ℹ️ [_ensure_window_on_current_desktop] 多桌面支持: 使用默认窗口管理")
            
        except Exception as e:
            print(f"⚠️ [_ensure_window_on_current_desktop] 多桌面处理异常: {e}")
            import traceback
            print(f"⚠️ [_ensure_window_on_current_desktop] 详细错误: {traceback.format_exc()}")
        
        print("🔍 [_ensure_window_on_current_desktop] 多桌面检查完成")

    def on_focus_in(self, event=None):
        """窗口获得焦点时的处理"""
        # 取消自动隐藏定时器
        if self.auto_hide_timer:
            self.root.after_cancel(self.auto_hide_timer)
            self.auto_hide_timer = None
    
    def on_focus_out(self, event=None):
        """窗口失去焦点时的处理"""
        # 窗口显示逻辑只根据取词状态决定，不自动隐藏
        pass
    
    def auto_hide_if_not_focused(self):
        """如果窗口没有焦点，自动隐藏"""
        # 窗口显示逻辑只根据取词状态决定，不自动隐藏
        pass
    
    def clean_punctuation(self, text):
        """清理文本前后的标点符号"""
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
    
    def adjust_window_position(self):
        """智能调整窗口位置，避免遮挡取词位置"""
        if not self.last_mouse_position:
            return
            
        mouse_x, mouse_y = self.last_mouse_position
        
        # 获取屏幕尺寸
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 获取窗口尺寸
        window_width = 500
        window_height = 400
        
        # 计算安全距离（避免窗口紧贴屏幕边缘）
        margin = 20
        
        # 根据鼠标位置选择最佳显示区域
        # 将屏幕分为4个象限，选择远离鼠标的象限
        screen_center_x = screen_width // 2
        screen_center_y = screen_height // 2
        
        if mouse_x < screen_center_x and mouse_y < screen_center_y:
            # 鼠标在左上角，窗口放在右下角
            x = screen_width - window_width - margin
            y = screen_height - window_height - margin
        elif mouse_x >= screen_center_x and mouse_y < screen_center_y:
            # 鼠标在右上角，窗口放在左下角
            x = margin
            y = screen_height - window_height - margin
        elif mouse_x < screen_center_x and mouse_y >= screen_center_y:
            # 鼠标在左下角，窗口放在右上角
            x = screen_width - window_width - margin
            y = margin
        else:
            # 鼠标在右下角，窗口放在左上角
            x = margin
            y = margin
        
        # 应用新的窗口位置
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 确保窗口在屏幕范围内
        self.root.update_idletasks()
        
    def set_mouse_position(self, x, y):
        """记录鼠标取词位置"""
        self.last_mouse_position = (x, y)
    
    def handle_captured_word(self, word, mouse_x=None, mouse_y=None):
        """处理捕获到的单词"""
        # 使用状态管理器处理新单词
        result = self.word_state_manager.handle_new_word(word)
        
        # 调试信息
        print(f"DEBUG DictionaryApp: 处理结果={result}")
        
        if not result['should_process']:
            # 不需要处理的情况：空单词或相同单词
            print(f"DEBUG DictionaryApp: 跳过处理，原因: {result['reason']}")
            return
        
        # 记录鼠标位置（如果提供了）
        if mouse_x is not None and mouse_y is not None:
            self.set_mouse_position(mouse_x, mouse_y)
        
        # 在GUI线程中更新界面
        self.root.after(0, lambda: self._process_captured_word(result['cleaned_word']))
    
    def _process_captured_word(self, word):
        """在GUI线程中处理捕获的单词"""
        print(f"🔍 [_process_captured_word] 开始处理捕获的单词: '{word}'")
        
        # 状态管理器已经处理了单词比较，这里直接处理新单词
        print(f"DEBUG DictionaryApp: 处理新单词 '{word}'")
        
        # 更新状态管理器中的当前单词
        self.word_state_manager.update_current_word(word)
        
        # 显示窗口（只根据取词状态决定）
        print("🔍 [_process_captured_word] 调用show_window()")
        self.show_window()
        
        # 智能调整窗口位置，避免遮挡取词位置
        print("🔍 [_process_captured_word] 调用adjust_window_position()")
        self.adjust_window_position()
        
        # 临时置顶窗口以便查看结果
        self.root.attributes('-topmost', True)
        print("🔍 [_process_captured_word] 窗口已置顶")
        
        # 更新输入框（只有不同单词才更新）
        self.entry.delete(0, END)
        self.entry.insert(0, word)
        
        # 自动搜索
        print("🔍 [_process_captured_word] 开始自动搜索")
        self.search()
        
        # 显示捕获提示
        self.show_capture_notification(word)
        
        # 3秒后取消置顶（如果用户没有手动置顶）
        self.root.after(3000, self._restore_window_state)
        
        print("🔍 [_process_captured_word] 单词处理完成")
    
    def _restore_window_state(self):
        """恢复窗口状态"""
        # 如果用户没有手动置顶，取消置顶
        if not self.root.attributes('-topmost'):
            return
            
        # 检查窗口按钮状态
        if self.window_btn.cget('text') == "置顶显示":
            self.root.attributes('-topmost', False)
    
    def show_capture_notification(self, word):
        """显示捕获成功的通知"""
        # 创建临时通知标签
        notification = Label(self.top_frame, text=f"已捕获: {word}", 
                           font=("Arial", 10), fg="blue", bg="lightyellow")
        notification.pack(side=RIGHT, padx=10)
        
        # 3秒后自动移除通知
        self.root.after(3000, notification.destroy)
    
    def search(self):
        word = self.entry.get().strip()
        if not word:
            return
        
        # 清空结果区域
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # 显示加载中
        loading_label = Label(self.scrollable_frame, text="Loading...", font=("Arial", 12))
        loading_label.pack()
        self.root.update()
        
        # 在新线程中执行搜索
        def search_thread():
            try:
                data = query_word(word)
                self.root.after(0, lambda: self._display_result(data, loading_label))
            except Exception as e:
                self.root.after(0, lambda: self._search_error(e, loading_label))
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    def _display_result(self, data, loading_label):
        """显示搜索结果"""
        loading_label.destroy()
        self.current_data = data
        self.display_result(data)
    
    def _search_error(self, error, loading_label):
        """处理搜索错误"""
        loading_label.destroy()
        messagebox.showerror("Error", str(error))
    
    def display_result(self, data):
        word = data.get("word", "")
        
        word_label = Label(self.scrollable_frame, text=word, font=("Arial", 24, "bold"))
        word_label.pack(pady=(0, 10))
        
        # 检查是否为多单词短语
        is_phrase = data.get("is_phrase", False)
        result_type = data.get("result_type", "")
        
        if is_phrase:
            # 显示短语翻译结果
            translation = data.get("translation", "")
            from_lang = data.get("from_language", "")
            to_lang = data.get("to_language", "")
            suggestion = data.get("suggestion", "")
            
            if translation:
                translation_frame = Frame(self.scrollable_frame)
                translation_frame.pack(fill=X, pady=10)
                
                # 根据结果类型显示不同的标题
                if result_type == "phrase_translation":
                    Label(translation_frame, text="翻译:", font=("Arial", 12, "bold")).pack(anchor=W)
                elif result_type == "keyword_detection":
                    Label(translation_frame, text="提示:", font=("Arial", 12, "bold"), fg="orange").pack(anchor=W)
                
                # 创建翻译文本和播放按钮的框架
                trans_text_frame = Frame(translation_frame)
                trans_text_frame.pack(fill=X, anchor=W)
                
                trans_label = Label(trans_text_frame, text=translation, 
                                  font=("Arial", 14), fg="#333", wraplength=400, justify=LEFT)
                trans_label.pack(side=LEFT, anchor=W)
                
                # 为短语翻译添加播放按钮（如果有TTS音频）
                ph_tts_mp3 = data.get("symbols", {}).get("ph_tts_mp3", "")
                if ph_tts_mp3:
                    play_btn = Button(trans_text_frame, text="🔊", fg="green", cursor="hand2",
                                     font=("Arial", 12), command=lambda: play_audio(ph_tts_mp3))
                    play_btn.pack(side=LEFT, padx=(10, 0))
                
                if from_lang and to_lang:
                    lang_label = Label(translation_frame, text=f"{from_lang} → {to_lang}", 
                                     font=("Arial", 10), fg="#666")
                    lang_label.pack(anchor=W)
                
                if suggestion:
                    suggest_label = Label(translation_frame, text=suggestion, 
                                        font=("Arial", 11), fg="blue", wraplength=450, justify=LEFT)
                    suggest_label.pack(anchor=W, pady=(5, 0))
        else:
            # 单个单词的显示逻辑
            symbols = data.get("symbols", {})
            
            if symbols:
                word_symbol = symbols.get("word_symbol", "")
                if word_symbol:
                    Label(self.scrollable_frame, text=f"[{word_symbol}]", font=("Arial", 14)).pack()
                
                ph_en = symbols.get("ph_en", "")
                ph_am = symbols.get("ph_am", "")
                ph_en_mp3 = symbols.get("ph_en_mp3", "")
                ph_am_mp3 = symbols.get("ph_am_mp3", "")
                ph_tts_mp3 = symbols.get("ph_tts_mp3", "")
                
                if ph_en or ph_am:
                    pron_frame = Frame(self.scrollable_frame)
                    pron_frame.pack(pady=5)
                    
                    if ph_en:
                        en_btn = Button(pron_frame, text=f"EN: {ph_en}", fg="blue", cursor="hand2",
                                       font=("Arial", 11), command=lambda: play_audio(ph_en_mp3))
                        en_btn.pack(side=LEFT, padx=5)
                    
                    if ph_am:
                        am_btn = Button(pron_frame, text=f"AM: {ph_am}", fg="blue", cursor="hand2",
                                       font=("Arial", 11), command=lambda: play_audio(ph_am_mp3))
                        am_btn.pack(side=LEFT, padx=5)
                    
                    # 添加TTS播放按钮
                    if ph_tts_mp3:
                        tts_btn = Button(pron_frame, text="🔊 TTS", fg="green", cursor="hand2",
                                        font=("Arial", 11), command=lambda: play_audio(ph_tts_mp3))
                        tts_btn.pack(side=LEFT, padx=5)
                
                parts = symbols.get("parts", [])
                if parts:
                    meanings_frame = Frame(self.scrollable_frame)
                    meanings_frame.pack(fill=X, pady=10)
                    
                    Label(meanings_frame, text="Meanings:", font=("Arial", 12, "bold")).pack(anchor=W)
                    
                    for part in parts:
                        part_name = part.get("part", "")
                        means = part.get("means", [])
                        
                        if part_name and means:
                            part_label = Label(meanings_frame, text=f"{part_name}:", 
                                             font=("Arial", 11, "bold"), fg="#333")
                            part_label.pack(anchor=W, pady=(5, 0))
                            
                            means_text = ", ".join(means[:10])
                            mean_label = Label(meanings_frame, text=means_text, 
                                             font=("Arial", 10), fg="#555", wraplength=450, justify=LEFT)
                            mean_label.pack(anchor=W, padx=(10, 0))
        
        # 显示例句（如果有）
        sentences = data.get("sentences", [])
        if sentences:
            sentences_frame = Frame(self.scrollable_frame)
            sentences_frame.pack(fill=X, pady=10)
            
            Label(sentences_frame, text="例句:", font=("Arial", 12, "bold")).pack(anchor=W)
            
            for i, sentence in enumerate(sentences[:5]):  # 最多显示5个例句
                en_text = sentence.get("en", "")
                cn_text = sentence.get("cn", "")
                tts_url = sentence.get("ttsUrl", "")
                
                if en_text and cn_text:
                    # 创建例句框架
                    sentence_frame = Frame(sentences_frame)
                    sentence_frame.pack(fill=X, pady=5)
                    
                    # 为动态创建的例句框架绑定滚轮事件
                    self._bind_wheel_to_frame(sentence_frame)
                    
                    # 英文句子和播放按钮（播放按钮在前）
                    en_frame = Frame(sentence_frame)
                    en_frame.pack(fill=X, anchor=W)
                    
                    # 为英文句子框架绑定滚轮事件
                    self._bind_wheel_to_frame(en_frame)
                    
                    # 添加例句播放按钮（放在句子前面）
                    if tts_url:
                        play_btn = Button(en_frame, text="🔊", fg="green", cursor="hand2",
                                         font=("Arial", 10), width=1, height=1,
                                         command=lambda url=tts_url: play_audio(url))
                        play_btn.pack(side=LEFT, padx=(0, 5))
                        
                        # 为播放按钮绑定滚轮事件
                        self._bind_wheel_to_widget(play_btn)
                    
                    en_label = Label(en_frame, text=f"{i+1}. {en_text}", 
                                   font=("Arial", 11), fg="#333", wraplength=430, justify=LEFT)
                    en_label.pack(side=LEFT, anchor=W)
                    
                    # 为标签绑定滚轮事件
                    self._bind_wheel_to_widget(en_label)
                    
                    # 中文翻译
                    cn_label = Label(sentence_frame, text=f"   {cn_text}", 
                                   font=("Arial", 10), fg="#666", wraplength=430, justify=LEFT)
                    cn_label.pack(anchor=W, padx=(20, 0))
                    
                    # 为中文标签绑定滚轮事件
                    self._bind_wheel_to_widget(cn_label)
    
    def _bind_wheel_to_frame(self, frame):
        """为框架绑定滚轮事件"""
        def _on_frame_mousewheel(event):
            """处理框架内的鼠标滚轮事件"""
            # 正确的滚轮事件处理逻辑：
            # 向上滚动 (event.delta > 0): 视图向上移动，使用负数
            # 向下滚动 (event.delta < 0): 视图向下移动，使用正数
            delta = -1 * (event.delta // 120)  # 标准化滚轮值
            # 滚动Canvas
            self.canvas.yview_scroll(delta, "units")
        
        # 绑定滚轮事件到框架
        frame.bind("<MouseWheel>", _on_frame_mousewheel)
        frame.bind("<Button-4>", _on_frame_mousewheel)  # Linux向上滚动
        frame.bind("<Button-5>", _on_frame_mousewheel)  # Linux向下滚动
    
    def _bind_wheel_to_widget(self, widget):
        """为小部件绑定滚轮事件"""
        def _on_widget_mousewheel(event):
            """处理小部件内的鼠标滚轮事件"""
            # 正确的滚轮事件处理逻辑：
            # 向上滚动 (event.delta > 0): 视图向上移动，使用负数
            # 向下滚动 (event.delta < 0): 视图向下移动，使用正数
            delta = -1 * (event.delta // 120)  # 标准化滚轮值
            # 滚动Canvas
            self.canvas.yview_scroll(delta, "units")
        
        # 绑定滚轮事件到小部件
        widget.bind("<MouseWheel>", _on_widget_mousewheel)
        widget.bind("<Button-4>", _on_widget_mousewheel)  # Linux向上滚动
        widget.bind("<Button-5>", _on_widget_mousewheel)  # Linux向下滚动
    
    def on_closing(self):
        """窗口关闭时的处理"""
        if self.capture_mode:
            stop_service()
        self.root.destroy()


if __name__ == "__main__":
    root = Tk()
    app = DictionaryApp(root)
    root.mainloop()