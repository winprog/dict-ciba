"""UI 设计常量（P1 视觉体系）。

集中管理颜色 / 字体 / 间距，供 dictionary_gui 及后续拆分的各视图复用。
风格对照 docs/prototypes/ui-refactor.html 的 Proposed 变体。
"""

# ---------- 颜色（语义化） ----------
COLORS = {
    # 主色
    "primary": "#1565C0",          # 主操作（Search / LLM / 高亮）
    "primary_hover": "#0d47a1",
    "primary_text_on": "#FFFFFF",  # 主色上的文字

    # 状态色
    "success_bg": "#e8f5e9",
    "success_text": "#2e7d32",
    "success_led": "#28c840",
    "danger_bg": "#ffebee",
    "danger_text": "#c62828",
    "danger_border": "#ef9a9a",
    "neutral_bg": "#fafafa",
    "neutral_text": "#757575",
    "warning": "#ef6c00",        # 提示 / 警示文字

    # 文本层级
    "text_primary": "#212121",
    "text_secondary": "#616161",
    "text_disabled": "#9E9E9E",

    # 背景 / 边框
    "surface": "#FFFFFF",
    "card": "#f5f5f5",
    "border": "#e0e0e0",
    "separator": "#ddd",

    # 对话气泡
    "bubble_user": "#1565C0",      # LLM 用户气泡
    "bubble_ai": "#f5f5f5",        # LLM AI 气泡
    "bubble_user_text": "#FFFFFF",
    "bubble_ai_text": "#212121",
    "bubble_user_text_bg": "#e3f0fd",   # 旧用户气泡底色（兼容过渡）
}

# ---------- 字体（层级） ----------
FONTS = {
    "title": ("Arial", 24, "bold"),      # 单词主标题
    "heading": ("Arial", 16, "bold"),    # 短语标题
    "subheading": ("Arial", 14, "bold"), # 小节标题 / 音标
    "body": ("Arial", 13),               # 正文
    "body_bold": ("Arial", 12, "bold"),  # 加粗正文
    "label": ("Arial", 12),              # 普通标签
    "label_bold": ("Arial", 12, "bold"),
    "small": ("Arial", 10),              # 说明 / 次要信息
    "caption": ("Arial", 9),             # 辅助文本 / 工具按钮
    "input": ("Arial", 14),              # 输入框
    "italic": ("Arial", 11, "italic"),   # 长引文
}

# ---------- 间距（spacing scale） ----------
SPACING = {
    "XS": 4,   # 元素内部极细微间隔
    "S": 8,    # 元素间小间隔
    "M": 12,   # 中等间距
    "L": 16,   # 区块间距 / 控件 padding
    "XL": 24,  # 大区块间距
}
# 常用组合（pack 用）
PAD = {
    "input_row": 10,     # 输入行上下 padding
    "result_h": 10,      # 结果区水平 padding
    "result_v": 10,      # 结果区垂直 padding
    "pad_xs": 2,         # 贴边极窄间隔（气泡间）
    "pad_s": 5,          # 同排元素/发音按钮间隔
    "pad_m": 6,          # 输入框内侧间隔
    "pad_l": 8,          # 小节下距
    "pad_md": 10,        # 通用中距
    "pad_lg": 12,        # 追问行上距
    "indent": 20,        # 例句中文缩进
}