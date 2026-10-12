# 屏幕取词去除剪贴板回退，仅用 PRIMARY（方案3）

出现「选中段落时翻译的却是上次粘贴的问题」：取词在 PRIMARY 读不到时回退读 CLIPBOARD，把陈旧剪贴板内容当成了当前选中。决定：**取词只认 PRIMARY，取消/收紧 CLIPBOARD 兜底**——PRIMARY 读不到就返回空，宁可漏词也不翻译错词，彻底屏蔽剪贴板对取词的干扰。该决定仅改翻译程序自身（`word_capture_service.py`），不需要任何系统配置。

## Status

accepted

## Context

项目的 `get_selected_text()` 按 `["primary", "clipboard"]` 取词，PRIMARY 读不到时静默回退 CLIPBOARD。运行环境为 GNOME + Wayland（X11 桥接），部分 Wayland 原生应用的 PRIMARY 未必同步到 XWayland，导致 `xclip -selection primary -o` 失败，落到 CLIPBOARD 读取用户粘贴/复制的陈旧内容，产生「翻译了刚才粘贴的问题」。

## Decision

取词以 PRIMARY 为准：PRIMARY 读到有效且变化的内容才触发翻译；PRIMARY 缺失时不再把 CLIPBOARD 陈旧内容当作新选中喂给翻译程序。改动范围仅限翻译程序内，不新增系统依赖与配置。这是「正确性优先于覆盖」的取舍。

## Considered Options

- **方案 1 / AT-SPI2**（使用辅助功能总线读焦点应用选中文本，零打扰、对浏览器/GTK 通吃）→ **弃用暂缓**：需安装系统包 + 一次性辅助功能授权 + 处理 venv 无法直接装系统 pyatspi 的问题，且终端/自定义控件常无文本接口；成本高于当前收益。
- **方案 2 / OCR**（截图识别，不依赖任何应用选中机制）→ **弃用**：慢（200-800ms）、需剪字库，不适合作为主路径。
- **方案 3 / 仅 PRIMARY**（本决定）→ **采用**：改动最小、零系统配置，立即根治「粘旧文」。

## Consequences

- **正确性**：不再把陈旧剪贴板内容误判为选中，消除「粘贴内容干扰取词」。
- **覆盖**：对 PRIMARY 未同步的 Wayland 原生应用会漏词（宁可漏词也不翻译错词）。
- **后续触发条件**：若日常取词源应用多为 Wayland 原生且漏词明显，**评估方案 1（AT-SPI2）作为叠加取词源**，PRIMARY 为主、AT-SPI 补充。