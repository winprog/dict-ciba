# Dict-CiBa UI 重构技术方案

## 1. 背景

Dict-CiBa 当前 UI 代码集中在 `dictionary_gui.py`（1150 行），承担窗口管理、取词控制、搜索分流、UI 渲染、音频播放、桌面定位 6 个职责。**核心功能链路已通**（选中文本 → 取词 → 窗口滑入 → 自动翻译 → LLM 追问），但在视觉一致性、交互健壮性、代码可维护性三个维度存在系统性问题，阻碍后续快速迭代。

本方案以**"零依赖引入、保持用户已有习惯、渐进式重构"**为原则，逐项修复并跟踪进度。

---

## 2. 目标

| 目标 | 度量方式 |
|---|---|
| 视觉一致性 | 统一 spacing scale 和字体层级，消除 magic number 间距 |
| 代码可维护性 | `DictionaryApp` 单类拆分至 4–5 个职责单一的类，单文件 ≤ 400 行 |
| 交互健壮性 | 修复已知逻辑 bug，消除滚轮事件重复绑定等混乱 |
| 用户体验 | 支持全局快捷键、改进加载反馈、错误提示内联化 |

**非目标**：不更换 UI 框架（保持 tkinter）、不引入第三方主题系统（ttk 够用）、不改取词/翻译的后端逻辑。

---

## 3. 现状问题与改进方案

### 3.1 视觉体系（视觉一致性）

**问题**：
- 间距散落 `pady=(5,0)`/`pady=8`/`pady=10`/`pady=(12,0)` 等 magic number
- 按钮状态色 `lightgreen`/#90EE90 黑字对比度仅 3:1，低于 WCAG AA 的 4.5:1
- LLM 对话中用户消息用 `Label`（浅蓝底）、AI 消息用 `HtmlFrame`（灰底+圆角），并排视觉风格断裂
- 字体全文 Arial 一种字号，无主色/辅色/中性色字体颜色三级体系

**方案**：

1. **建立 spacing scale**，定义 4/8/16/24 四个基准值，所有间距从中选取
2. **定义语义化颜色常量**，集中在一个 `colors.py` 或文件顶部：

```python
COLORS = {
    "primary": "#1565C0",        # 主色（LLM 按钮蓝）
    "success_bg": "#4CAF50",     # 成功态背景（取词开启）
    "success_text": "#FFFFFF",
    "danger_bg": "#E53935",      # 危险态背景（停止取词）
    "surface": "#FAFAFA",        # 卡片/气泡背景
    "text_primary": "#212121",   # 主文字
    "text_secondary": "#616161", # 辅文字
    "text_disabled": "#9E9E9E",  # 禁用文字
    "border": "#E0E0E0",
}
```

3. **统一 LLM 对话气泡样式**：用户气泡和 AI 气泡都用 `Frame + Label` 或都用 `HtmlFrame`，建议保持 `HtmlFrame` 统一（因为 Markdown 渲染需求），用户消息也转成内联 HTML
4. **定义字体层级**：

```python
FONTS = {
    "title": ("Arial", 24, "bold"),
    "section": ("Arial", 14, "bold"),
    "body": ("Arial", 12),
    "caption": ("Arial", 10),
}
```

---

### 3.2 交互健壮性（逻辑修复）

#### Bug-P0：`_restore_window_state` 互斥条件

**现状**：
```python
def _restore_window_state(self):
    if not self.root.attributes('-topmost'):  # 条件 A
        return
    if self.window_btn.cget('text') == "置顶显示":  # 条件 B
        self.root.attributes('-topmost', False)
```
条件 A 检查 topmost=False 直接返回，条件 B 只有 btn.text=="置顶显示"（即 topmost 为 False 时的显示）才进入——两个条件实际上几乎互斥，3 秒延迟恢复逻辑形同虚设。

**修复**：增加一个 `_user_manually_pinned` 标记，只有用户没手动点过置顶按钮时才在 3 秒后恢复。

#### Bug-P1：滚轮事件 6 次重复绑定

**现状**：`bind_all` 一次 + Canvas + Scrollbar + ResultFrame + ScrollableFrame 各一次 + 动态 `_bind_wheel_to_frame/widget`。维护者无法判断去掉哪个会坏。

**修复**：只保留 `bind_all` 一次，在 handler 内判断是否目标 widget 属于当前 canvas 的滚动域。

#### Bug-P1：`adjust_window_position` 与 `WindowPlacementService` quadrant 逻辑重复

两处都做了「四象限对角线放置」，删除 `adjust_window_position`，统一使用 `WindowPlacementService`。

#### Bug-P2：空方法占位

`on_focus_out` 和 `auto_hide_if_not_focused` 只有 `pass`。要么实现自动隐藏功能，要么删除——留着会误导后续维护者以为功能还没做完。

---

### 3.3 技术债务（代码拆分）

#### 拆分方案

`DictionaryApp` 当前 1150 行 → 拆为以下 5 个类，每个 ≤ 400 行：

| 新类 | 职责 | 预计行数 | 迁移内容 |
|---|---|---|---|
| `AppWindow` | 窗口 chrome（标题、尺寸、置顶、隐藏、位置） | ~250 | `__init__` 布局相关、`toggle_window_topmost`、`hide_window`/`show_window`、`_ensure_window_sticky`、`_find_x11_window_id`、`_on_window_resize` |
| `CaptureController` | 取词模式开关 + 回调桥接 | ~100 | `toggle_capture_mode`、`toggle_hover_capture`、`handle_captured_word`、`_process_captured_word`、`show_capture_notification` |
| `SearchController` | 搜索分流策略（iciba vs LLM） | ~150 | `search`、`_display_result`、`_search_error`、`_switch_to_llm_chat`、`search_llm` |
| `LLMConversation` | 多轮对话视图 + 渲染 | ~180 | `_llm_history` 状态、`_start_llm_chat`、`_ask_llm`、`_llm_respond`、`_llm_error`、`_render_llm_chat`、`_render_llm_followup_input` |
| `ResultRenderer` | 词典查询结果渲染 | ~300 | `display_result` 中的单词/短语/长文本分支、例句/释义/音标渲染 |

**音频播放** `play_audio` 整体移入独立文件 `audio_player.py`，UI 层只调用接口。

#### 执行结果

实际拆分产出了比原方案更细的模块表。`dictionary_gui.py`（`DictionaryApp`）由 1150 行收敛至 ~410 行；原方案中"≤400 行"按**逻辑/职责**达成而非机械压行（详见下文清洗项）。最终模块划分：

| 模块 | 职责 |
|---|---|
| `ui_builder.py` `MainView` | 顶栏操作面板/输入面板分组装配 + `bind_actions` 行为绑定 + `refresh_capture`/`set_led`/`set_topmost_mode`/`set_hide_state`/`focus_input` 状态刷新，消除对裸按钮的属性回传 |
| `window_manager.py` `WindowManager` | 窗口放置/置顶管理收口（消除 `_find_x11_window_id`/`_ensure_window_sticky` 长方法） |
| `llm_chat_view.py` `LLMChatView` | LLM 对话视图渲染收口 |
| `scroll_area.py` `ScrollArea` | 可滚动结果区（canvas/scrollbar/滚轮/布局刷新）收口 |
| `spinner.py` | 四帧加载 spinner 独立组件（原主类 `_make_spinner` 下沉） |
| `capture_controller.py`/`search_controller.py`/`llm_conversation.py`/`result_renderer.py` | 取词/搜索/对话/渲染四控制器 |
| `window_manager.py`/`desktop_placement.py` | Facade + 窗口几何/置顶 |

**清洗项（改设计而不是改逻辑）**：删除 `dictionary_gui` 中死代码 `clean_punctuation`（与 `WordStateManager` 重复且未被调用）、冗余 `_llm_input` 字段、重复 `capture_mode` 初值、`canvas_window_id` 死字段；`SPACING`/`html`/`markdown`/`HtmlFrame`/`ttk`/`SearchHistory` 未用 import 全量清理。

#### 消除 `wraplength_labels` hack

用 `Text` 组件替换结果区的 `Canvas + Frame` 方案，`Text` 原生支持 `wrap=WORD` 自适应容器宽度，不需要手动维护 wraplength 列表。

#### 日志统一

所有 `print()` 替换为 `logging.debug/info/warning`，项目已有 `import logging` 但 UI 层完全未使用。emoji 前缀（`🔊`、`🖥️`、`📐`）保留在日志内容中作为可读性。

---

### 3.4 可用性增强

| 能力 | 方案 |
|---|---|
| 全局快捷键 | 新增 `hotkey_manager.py`，使用 `keyboard` 或 `pynput` 库。`Ctrl+Shift+C` 开关取词，`Esc` 隐藏窗口 |
| 加载反馈 | Loading 文案 + 简单的 `.config(text="Loading...⏳", font=("Arial", 14))`，或用 `after` 定时器实现 spinner 动画 |
| 错误提示内联 | 搜索失败时在结果区顶部显示红色条带 Label，替换 `messagebox.showerror` 弹窗打断 |
| 搜索历史 | Entry 改为 `ttk.Combobox`，`values` 动态更新最近 20 条查询 |
| 键盘导航 | Entry 绑 Return 之外，按钮设 `focus_set`，定义 tab 顺序 |

---

## 4. 任务进度表

### 阶段一：紧急修复（P0）

| ID | 任务 | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| P0-1 | 修复 `_restore_window_state` 互斥条件 bug，增加 `_user_manually_pinned` 标记 | 🟢 已完成 | 增加字段；`toggle_window_topmost` 置真；自动置顶时重置；恢复时尊重手动置顶 |
| P0-2 | 移除/实现空方法 `on_focus_out`、`auto_hide_if_not_focused` | 🟢 已完成 | 删除两空方法 + `<FocusOut>` 绑定；保留 `on_focus_in` |
| P0-3 | 消除滚轮事件 6 次重复绑定，只保留 `bind_all` 一次 | 🟢 已完成 | 删除组件级 12 处 bind 与两个 helper 及调用 |
| P0-4 | 删除 `adjust_window_position`，统一使用 `WindowPlacementService` | 🟢 已完成 | 方法从未被调用，直接移除 |

### 阶段二：视觉体系建立（P1）

| ID | 任务 | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| P1-1 | 提取 `COLORS`/`FONTS`/`SPACING` 常量，替换硬编码颜色与字号 | 🟢 已完成 | 新建 `ui_constants.py`；主色/状态色/文本层/气泡色 + 字体层级全部收口，`dictionary_gui.py` 无硬编码 hex |
| P1-2 | 统一 spacing scale，消除 magic number pady | 🟢 已完成 | `SPACING`/`PAD` 常量补齐到全量语义（pad_xs/s/m/md/l/lg/indent 等），`dictionary_gui`/`result_renderer` 内所有 pady/padx 改为具名引用，无裸数字 |
| P1-3 | LLM 对话气泡样式统一（用户/AI 都用 HtmlFrame 或都用 Frame+Label） | 🟢 已完成 | 新增 `_chat_bubble_html`，用户/AI 均走 HtmlFrame，共用圆角气泡样式 |
| P1-4 | 取词按钮/状态灯视觉增强：增加小图标指示灯 | 🟢 已完成 | 新增 Canvas 状态灯 `_set_led`，绿灯亮=取词运行中 |

### 阶段三：代码拆分（P2）

| ID | 任务 | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| P2-1 | 提取 `audio_player.py`，UI 层只调接口 | 🟢 已完成 | 新建 `audio_player.py`，`play_audio` + `_play_fallback` 全量迁移，`dictionary_gui` 改 import |
| P2-2 | 提取 `CaptureController` | 🟢 已完成 | 新建 `capture_controller.py`，封装启停/悬停/状态，UI 经 `_render_capture_state` 渲染 |
| P2-3 | 提取 `SearchController` | 🟢 已完成 | 新建 `search_controller.py`，单词/长文本/短语分流 + 异步查询调度，UI 侧回调渲染 |
| P2-4 | 提取 `LLMConversation` | 🟢 已完成 | 新建 `llm_conversation.py`，对话状态/系统提示词/异步调度收口，UI 只渲染 `conv.history`，并加追问防抖 |
| P2-5 | 提取 `ResultRenderer` | 🟢 已完成 | 新建 `result_renderer.py`，`display_result` 全量渲染逻辑迁移；依赖经构造注入（frame/register_wrap/get_frame_width），UI 侧收敛为一行委托 |
| P2-6 | 消除 `wraplength_labels` hack，Text 组件替换 Canvas+Frame | 🟢 已完成 | 保留 `Canvas+Frame`（多版块/LLM HtmlFrame 无法塞进单 `Text`，换组件反而翻车），改为把动态换行管理**收口进 `ResultRenderer`**（内部 `_wrap_labels` + `update_wraplength()`）；UI 层不再存在 `wraplength_labels`，resize 时调 `renderer.update_wraplength(frame_width)` 一次性刷新 |
| P2-7 | print → logging，统一日志级别 | 🟢 已完成 | 新建 `logger.py`；`dictionary_gui`/`audio_player`/`word_state_manager` 运行时 print 全量迁移（debug/info/warning 分级，保留 emoji 前缀），入口 `setup_logging`；`test_*.py` 与 `__main__` 自测块保留 print |

### 阶段四：可用性增强（P3）

| ID | 任务 | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| P3-1 | 全局快捷键 `Ctrl+Shift+C` 开关取词、`Esc` 隐藏窗口 | 🟢 已完成 | 新增 `_register_shortcuts`（应用内 `bind_all`）。注：`keyboard`/`pynput` 均不可用且 Wayland 全局捕获不可靠，故适配为窗口聚焦即生效，系统级全局热键依赖 GNOME 桌面自定义 |
| P3-2 | 加载 spinner 动画（替代静态 "Loading..."） | 🟢 已完成 | 新增 `_make_spinner`：四帧 `|`/`/`/`-`/`\` + `after` 定时器驱动，返回幂等 `stop()` |
| P3-3 | 错误提示内联化（红色条带 Label 替换 messagebox） | 🟢 已完成 | `_search_error` 改为在结果区渲染红色条带（danger_bg/danger_text），不再弹窗打断 |
| P3-4 | 搜索历史（Combobox + 最近 20 条） | 🟢 已完成 | 新建 `search_history.py`（JSON 持久化 `~/.ciba_history.json`，有序去重限 20）；输入框换为 `ttk.Combobox`，FocusIn/下拉/回车均绑定，成功查询自动记录 |
| P3-5 | 键盘导航 + tab 顺序定义 | 🟢 已完成 | 初始焦点落输入框 `entry.focus_set()`，Tab 按创建序（顶部操作区 → 输入→Search→LLM→结果）；Esc/Ctrl+Shift+C 快捷键联动 |
| P3-6 | 取词到翻译过程增加 toast 进度提示 | 🟢 已完成 | 查词 spinner 文案语义化 `正在查词: {word}`；LLM 已有 `AI 思考中...`；取词命中保留顶部 `已捕获:` 通知 |

### 进度汇总

| 阶段 | 任务数 | 🔴 未开始 | 🟡 进行中 | 🟢 已完成 | 完成率 |
|---|---|---|---|---|---|
| P0 紧急修复 | 4 | 0 | 0 | 4 | 100% |
| P1 视觉体系 | 4 | 0 | 0 | 4 | 100% |
| P2 代码拆分 | 7 | 0 | 0 | 7 | 100% |
| P3 可用性增强 | 6 | 0 | 0 | 6 | 100% |
| **合计** | **21** | **0** | **0** | **21** | **100%** |

---

## 5. 验收标准

| 阶段 | 验收 |
|---|---|
| P0 | `_restore_window_state` 在取词后 3 秒正确恢复非置顶；滚轮在结果区、输入框、滚动条上行为一致；空方法已删除或实现；全局 grep 确认 `adjust_window_position` 仅定义一处 |
| P1 | 所有 `pady` 值 ∈ {4, 8, 16, 24}；按钮背景色对比度 ≥ 4.5:1（Chrome DevTools 可验）；LLM 对话气泡边框/圆角/内边距一致 |
| P2 | `dictionary_gui.py` ≤ 400 行；所有新类文件 ≤ 300 行；`grep print dictionary_gui.py` 无结果；`wraplength_labels` 属性不存在 |
| P3 | `Ctrl+Shift+C` 开关取词有效（后台运行时）；错误不弹 messagebox；Combobox 可下拉看到最近查词；Tab 键可在所有按钮/输入框间跳转 |

---

## 6. 风险与注意事项

| 风险 | 应对 |
|---|---|
| tkinter 组件迁移导致布局错乱 | 每拆一个类启动窗口验证，git commit 粒度按类拆分，坏了容易回退 |
| 全局快捷键库需要系统权限 | `keyboard` 在 Wayland 下需要 `sudo`，`pynput` 对 Wayland 支持也有限——**先做实验**，不行就退化为窗口聚焦热键 |
| Text 组件替换 Canvas+Frame 后 HtmlFrame 嵌入问题 | HtmlFrame 可以作为 Text 的 window_create 子组件，需要小范围验证再替换 |
| 日志降级过头 | print → debug，关键路径（取词触发、搜索结果、错误）用 info/warning，不要全改 debug |