import json
import re
import requests
import tempfile
import subprocess
import threading
import sys
import os
from typing import Optional, Dict, Any
from tkinter import *
from tkinter import messagebox

# 导入取词服务
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from word_capture_service import get_service, start_service, stop_service, on_capture


def query_word(word: str) -> Dict[str, Any]:
    url = f"https://www.iciba.com/word?w={word}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
    if not match:
        raise ValueError("Failed to find word data on the page")
    
    data = json.loads(match.group(1))
    word_info = data.get("props", {}).get("pageProps", {}).get("initialReduxState", {}).get("word", {}).get("wordInfo", {})
    
    if not word_info:
        raise ValueError(f"Word '{word}' not found")
    
    return _parse_word_info(word_info)


def _parse_word_info(word_info: Dict) -> Dict[str, Any]:
    result = {
        "word": word_info.get("baesInfo", {}).get("word_name", ""),
        "exchanges": word_info.get("exchanges", []),
    }
    
    symbols = word_info.get("baesInfo", {}).get("symbols", [])
    if symbols:
        symbol = symbols[0]
        result["symbols"] = {
            "word_symbol": symbol.get("word_symbol", ""),
            "ph_en": symbol.get("ph_en", ""),
            "ph_am": symbol.get("ph_am", ""),
            "ph_en_mp3": symbol.get("ph_en_mp3", ""),
            "ph_am_mp3": symbol.get("ph_am_mp3", ""),
            "ph_tts_mp3": symbol.get("ph_tts_mp3", ""),
            "parts": symbol.get("parts", []),
        }
        
        from_symbols_mean = symbol.get("fromSymbolsMean", [])
        if from_symbols_mean:
            result["symbols"]["from_symbols_mean"] = from_symbols_mean
    
    return result


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
        self.root.geometry("500x400")
        
        # 取词服务状态
        self.capture_mode = False
        
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
                messagebox.showinfo("取词模式", "取词模式已启动，请将鼠标悬停在单词上或选中文本进行取词")
            except Exception as e:
                messagebox.showerror("错误", f"启动取词服务失败: {e}")
        else:
            # 停止取词模式
            stop_service()
            self.capture_mode = False
            self.capture_btn.config(text="启动取词模式", bg="lightgreen")
            self.status_label.config(text="取词模式: 关闭", fg="gray")
            messagebox.showinfo("取词模式", "取词模式已停止")
    
    def handle_captured_word(self, word):
        """处理捕获到的单词"""
        if not word or len(word.strip()) == 0:
            return
            
        # 在GUI线程中更新界面
        self.root.after(0, lambda: self._process_captured_word(word))
    
    def _process_captured_word(self, word):
        """在GUI线程中处理捕获的单词"""
        # 更新输入框
        self.entry.delete(0, END)
        self.entry.insert(0, word)
        
        # 自动搜索
        self.search()
        
        # 显示捕获提示
        self.show_capture_notification(word)
    
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
        symbols = data.get("symbols", {})
        
        word_label = Label(self.scrollable_frame, text=word, font=("Arial", 24, "bold"))
        word_label.pack(pady=(0, 10))
        
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