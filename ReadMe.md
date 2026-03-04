# Dict-CiBa - 智能屏幕取词翻译工具

一个基于Python开发的智能屏幕取词翻译工具，支持鼠标悬停取词、自动翻译和智能窗口管理。

## 项目描述

Dict-CiBa是一个轻量级的桌面翻译工具，专门为需要频繁查阅英文单词含义的用户设计。通过智能的屏幕取词技术，用户可以快速获取鼠标悬停位置的单词翻译，无需手动输入或切换窗口。

## 主要功能

### 🎯 智能屏幕取词
- **鼠标悬停取词**：自动识别鼠标位置的英文单词
- **智能标点清理**：自动清理单词前后的标点符号
- **多源取词支持**：支持选中文本和剪贴板内容

### 🌐 金山词霸集成
- **权威词典**：集成金山词霸API，提供准确的单词释义
- **多维度信息**：包含音标、发音、词性、例句等完整信息
- **音频播放**：支持单词发音播放

### 🧠 智能状态管理 - **新增**
- **独立状态机**：专门的单词状态管理器类，分离关注点
- **智能单词比较**：清理标点符号后比较，准确识别相同单词
- **状态跟踪**：完整记录单词切换历史和捕获时间
- **调试支持**：详细的调试信息和状态查询

### 🪟 智能窗口管理
- **智能定位**：窗口自动显示在远离取词位置的对角线区域
- **自动隐藏**：窗口失去焦点后自动隐藏，减少视觉干扰
- **临时置顶**：取词时窗口临时置顶，方便查看结果
- **单词切换检测**：相同单词不重复显示窗口

### ⚡ 高效用户体验
- **无干扰操作**：取词过程不影响当前工作流程
- **快速响应**：毫秒级取词和翻译响应
- **自定义配置**：支持窗口透明度、置顶状态等个性化设置
- **架构优化**：模块化设计，便于维护和扩展

## 软件架构

### 核心模块

```
dict-ciba/
├── dictionary_gui.py      # 主GUI界面和窗口管理
├── word_capture_service.py # 屏幕取词服务
├── word_state_manager.py   # 单词状态管理器（新增）
├── iciba.py              # 金山词霸API接口
└── requirements.txt      # 项目依赖
```

### 架构设计

```
用户操作 → 屏幕取词服务 → 单词状态管理器 → GUI界面 → 金山词霸API
    ↓           ↓               ↓            ↓           ↓
鼠标悬停 → 单词捕获 → 状态检测和清理 → 窗口显示 → 翻译结果
```

### 核心组件

1. **GUI主界面 (dictionary_gui.py)**
   - Tkinter-based图形界面
   - 智能窗口位置管理
   - 用户交互和状态控制

2. **取词服务 (word_capture_service.py)**
   - 基于xdotool的鼠标位置追踪
   - 多线程取词监控
   - 剪贴板内容安全处理
   - 增强的重复检测逻辑

3. **单词状态管理器 (word_state_manager.py)** - **新增**
   - 独立的单词状态管理类
   - 智能标点符号清理
   - 单词切换检测和状态跟踪
   - 统一的调试和日志输出

4. **翻译引擎 (iciba.py)**
   - 金山词霸API封装
   - JSON数据解析
   - 错误处理和重试机制

## 技术依赖

### Python依赖

```bash
# requirements.txt
requests>=2.25.0
```

### 系统依赖

```bash
# Ubuntu/Debian系统
sudo apt install xdotool xclip python3-tk
```

### 运行环境

- **操作系统**: Linux (Ubuntu/Debian推荐)
- **Python版本**: Python 3.7+
- **桌面环境**: 支持X11的桌面环境

## 安装方法

### 1. 克隆项目

```bash
git clone https://github.com/winprog/dict-ciba.git
cd dict-ciba
```

### 2. 安装系统依赖

```bash
sudo apt update
sudo apt install xdotool xclip python3-tk
```

### 3. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 4. 运行应用

```bash
python3 dictionary_gui.py
```

## 使用方法

### 基本操作流程

1. **启动应用**

   ```bash
   python3 dictionary_gui.py
   ```
2. **启用取词模式**

   - 点击"启动取词模式"按钮
   - 状态指示灯变为绿色表示取词服务已启动
3. **开始取词**

   - 将鼠标悬停在需要翻译的英文单词上
   - 系统自动捕获单词并显示翻译结果
4. **窗口控制**

   - **置顶显示**: 临时将窗口置于最上层
   - **隐藏窗口**: 最小化窗口到任务栏
   - **自动隐藏**: 窗口失去焦点后自动隐藏

### 高级功能

#### 智能窗口定位

- 窗口会根据取词位置自动调整显示位置
- 左上角取词 → 窗口显示在右下角
- 右下角取词 → 窗口显示在左上角

#### 单词切换检测

- 相同单词不会重复显示窗口
- 只有新单词才会触发完整的取词流程

#### 标点符号清理

- 自动清理 `"hello"`, `'world'`, `（example）` 等格式的标点
- 确保查询的单词格式正确

## 开发指南

### 项目结构说明

```python
# dictionary_gui.py - 主界面类
class DictionaryApp:
    - 窗口管理和用户界面
    - 取词服务集成和回调处理
    - 智能位置调整算法
    - 使用WordStateManager进行单词状态管理

# word_state_manager.py - 单词状态管理器（新增）
class WordStateManager:
    - 独立的单词状态管理
    - 智能标点符号清理
    - 单词切换检测和状态跟踪
    - 统一的调试输出

# word_capture_service.py - 取词服务
class WordCaptureService:
    - 鼠标位置监控
    - 剪贴板内容获取
    - 多线程服务管理
    - 增强的重复检测逻辑

# iciba.py - 翻译接口
class ICiBa:
    - 金山词霸API调用
    - 翻译结果解析
    - 错误处理机制
```

### 扩展开发

#### 添加新的翻译源

```python
# 在iciba.py中添加新的翻译类
class NewTranslationService:
    def translate(self, word):
        # 实现新的翻译逻辑
        pass
```

#### 自定义窗口行为

```python
# 在dictionary_gui.py中修改窗口管理逻辑
def custom_window_behavior(self):
    # 实现自定义的窗口显示逻辑
    pass
```

#### 支持新的取词方式

```python
# 在word_capture_service.py中添加新的取词方法
def new_capture_method(self):
    # 实现新的取词逻辑
    pass
```

### 调试和测试

#### 查看取词服务日志

```bash
tail -f ~/.cache/word-capture/service.log
```

#### 测试取词功能

```bash
# 手动测试取词服务
python3 -c "from word_capture_service import get_service; service = get_service(); print(service.get_word_under_mouse())"
```

#### 测试翻译接口

```bash
# 测试金山词霸API
python3 -c "from iciba import ICiBa; translator = ICiBa(); result = translator.translate('hello'); print(result)"
```

## 故障排除

### 常见问题

#### 取词服务无法启动

**症状**: 点击"启动取词模式"后状态指示灯不变绿
**解决方案**:

```bash
# 检查xdotool和xclip是否安装
which xdotool
which xclip

# 检查服务日志
cat ~/.cache/word-capture/service.log
```

#### 窗口显示位置异常

**症状**: 窗口显示在屏幕外或位置不正确
**解决方案**:

- 重启应用
- 检查屏幕分辨率设置
- 验证鼠标位置获取功能

#### 翻译结果为空

**症状**: 取词成功但翻译结果为空
**解决方案**:

- 检查网络连接
- 验证金山词霸API可用性
- 查看控制台错误信息

### 性能优化

#### 减少资源占用

- 调整取词检测间隔时间
- 优化窗口重绘频率
- 使用更轻量的GUI组件

#### 提高响应速度

- 预加载常用单词翻译
- 实现本地缓存机制
- 优化网络请求并发

## 贡献指南

### 代码规范

- 遵循PEP 8编码规范
- 添加适当的类型提示
- 编写清晰的文档字符串

### 提交规范

- 使用有意义的提交信息
- 一个提交对应一个功能或修复
- 提交前进行充分的测试

### 功能建议

欢迎提交以下类型的功能建议：

- 新的翻译源集成
- 用户体验改进
- 性能优化方案
- 跨平台支持

## 许可证

本项目采用MIT许可证。详细信息请查看LICENSE文件。

## 更新日志

### v1.0.1 (2026-03-04)

#### 新增功能
- ✅ **单词状态管理器**: 独立的单词状态管理类，分离关注点
- ✅ **架构优化**: 模块化设计，便于维护和扩展
- ✅ **智能单词比较**: 清理标点符号后比较，准确识别相同单词
- ✅ **调试支持**: 详细的调试信息和状态查询

#### 改进优化
- ✅ **代码重构**: 提取单词状态逻辑到独立管理器
- ✅ **重复检测**: 增强的单词重复检测逻辑
- ✅ **文档更新**: 添加架构改进说明

### v1.0.0 (2026-03-04)

- ✅ 基础屏幕取词功能
- ✅ 金山词霸翻译集成
- ✅ 智能窗口位置管理
- ✅ 单词切换检测
- ✅ 标点符号清理
- ✅ 自动隐藏和显示

## 联系方式

- 项目主页: https://github.com/winprog/dict-ciba
- 问题反馈: https://github.com/winprog/dict-ciba/issues

---

**注意**: 本项目仍在积极开发中，欢迎提交反馈和建议！