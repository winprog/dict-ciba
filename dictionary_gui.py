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
    if not url:
        return
    
    def _play():
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                f.write(response.content)
                temp_path = f.name
            
            subprocess.run(['mpg123', '-q', temp_path], capture_output=True)
        except Exception as e:
            print(f"Failed to play audio: {e}")
    
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
        
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        
        self.current_data = None
        
        # 设置取词回调
        on_capture(self.handle_captured_word)
        
        # 窗口关闭时停止取词服务
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def toggle_capture_mode(self):
        """切换取词模式"""
        if not self.capture_mode:
            # 启动取词模式
            try:
                start_service()
                self.capture_mode = True
                self.capture_btn.config(text="停止取词模式", bg="lightcoral")
                self.status_label.config(text="取词模式: 运行中", fg="green")
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
        self.root.deiconify()  # 显示窗口
        self.window_visible = True
        self.hide_btn.config(text="隐藏窗口", bg="lightyellow")
        
        # 取消自动隐藏定时器
        if self.auto_hide_timer:
            self.root.after_cancel(self.auto_hide_timer)
            self.auto_hide_timer = None
    
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
        # 状态管理器已经处理了单词比较，这里直接处理新单词
        print(f"DEBUG DictionaryApp: 处理新单词 '{word}'")
        
        # 更新状态管理器中的当前单词
        self.word_state_manager.update_current_word(word)
        
        # 显示窗口（只根据取词状态决定）
        self.show_window()
        
        # 智能调整窗口位置，避免遮挡取词位置
        self.adjust_window_position()
        
        # 临时置顶窗口以便查看结果
        self.root.attributes('-topmost', True)
        
        # 更新输入框（只有不同单词才更新）
        self.entry.delete(0, END)
        self.entry.insert(0, word)
        
        # 自动搜索
        self.search()
        
        # 显示捕获提示
        self.show_capture_notification(word)
        
        # 3秒后取消置顶（如果用户没有手动置顶）
        self.root.after(3000, self._restore_window_state)
    
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
        
        if is_phrase:
            # 显示短语翻译结果
            translation = data.get("translation", "")
            from_lang = data.get("from_language", "")
            to_lang = data.get("to_language", "")
            
            if translation:
                translation_frame = Frame(self.scrollable_frame)
                translation_frame.pack(fill=X, pady=10)
                
                Label(translation_frame, text="翻译:", font=("Arial", 12, "bold")).pack(anchor=W)
                
                trans_label = Label(translation_frame, text=translation, 
                                  font=("Arial", 14), fg="#333", wraplength=450, justify=LEFT)
                trans_label.pack(anchor=W, pady=(5, 0))
                
                if from_lang and to_lang:
                    lang_label = Label(translation_frame, text=f"{from_lang} → {to_lang}", 
                                     font=("Arial", 10), fg="#666")
                    lang_label.pack(anchor=W)
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
    
    def on_closing(self):
        """窗口关闭时的处理"""
        if self.capture_mode:
            stop_service()
        self.root.destroy()


if __name__ == "__main__":
    root = Tk()
    app = DictionaryApp(root)
    root.mainloop()