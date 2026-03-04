#!/usr/bin/env python3
"""
单词状态管理器
负责管理单词的状态、比较和切换检测
"""

import time


class WordStateManager:
    """单词状态管理器"""
    
    def __init__(self):
        # 当前显示的单词（输入框中的内容）
        self.current_word = ""
        # 最后捕获的单词（取词服务捕获的原始内容）
        self.last_captured_word = ""
        # 最后捕获时间
        self.last_capture_time = 0
        # 调试模式
        self.debug_mode = True
    
    def clean_punctuation(self, text):
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
    
    def is_same_word(self, new_word, current_word=None):
        """
        判断两个单词是否相同（清理标点后比较）
        
        Args:
            new_word: 新捕获的单词
            current_word: 当前显示的单词，如果为None则使用内部记录的current_word
            
        Returns:
            bool: 是否相同
        """
        if current_word is None:
            current_word = self.current_word
            
        # 清理两个单词的标点符号
        cleaned_new = self.clean_punctuation(new_word)
        cleaned_current = self.clean_punctuation(current_word)
        
        # 调试信息
        if self.debug_mode:
            print(f"DEBUG WordStateManager: 新单词='{new_word}' -> '{cleaned_new}', "
                  f"当前单词='{current_word}' -> '{cleaned_current}', "
                  f"是否相同={cleaned_new == cleaned_current}")
        
        return cleaned_new == cleaned_current
    
    def handle_new_word(self, new_word):
        """
        处理新捕获的单词
        
        Args:
            new_word: 新捕获的单词
            
        Returns:
            dict: 处理结果，包含是否切换、清理后的单词等信息
        """
        # 清理新单词
        cleaned_word = self.clean_punctuation(new_word)
        
        # 检查是否为空
        if not cleaned_word:
            return {
                'should_process': False,
                'reason': 'empty_after_cleaning',
                'cleaned_word': '',
                'is_same_word': False
            }
        
        # 检查是否与当前单词相同
        is_same = self.is_same_word(new_word)
        
        if is_same:
            # 相同单词，不处理
            return {
                'should_process': False,
                'reason': 'same_word',
                'cleaned_word': cleaned_word,
                'is_same_word': True
            }
        else:
            # 不同单词，需要处理
            # 更新状态
            self.last_captured_word = new_word
            self.current_word = cleaned_word
            self.last_capture_time = time.time()
            
            return {
                'should_process': True,
                'reason': 'new_word',
                'cleaned_word': cleaned_word,
                'is_same_word': False
            }
    
    def update_current_word(self, word):
        """更新当前显示的单词"""
        self.current_word = word
        
    def get_state_info(self):
        """获取当前状态信息"""
        return {
            'current_word': self.current_word,
            'last_captured_word': self.last_captured_word,
            'last_capture_time': self.last_capture_time,
            'time_since_last_capture': time.time() - self.last_capture_time if self.last_capture_time else float('inf')
        }
    
    def set_debug_mode(self, enabled):
        """设置调试模式"""
        self.debug_mode = enabled
        
    def reset(self):
        """重置状态"""
        self.current_word = ""
        self.last_captured_word = ""
        self.last_capture_time = 0


# 测试函数
if __name__ == "__main__":
    # 创建状态管理器
    manager = WordStateManager()
    
    # 测试用例
    test_cases = [
        ("hello", "hello"),  # 相同单词
        ("hello!", "hello"),  # 带标点的相同单词
        ("hello", "world"),   # 不同单词
        ("", "hello"),        # 空单词
        ("hello.world", "hello"),  # 复杂标点
    ]
    
    print("=== WordStateManager 测试 ===")
    for i, (new_word, current_word) in enumerate(test_cases):
        print(f"\n测试 {i+1}: 新单词='{new_word}', 当前单词='{current_word}'")
        
        # 设置当前单词
        manager.current_word = current_word
        
        # 处理新单词
        result = manager.handle_new_word(new_word)
        
        print(f"结果: {result}")