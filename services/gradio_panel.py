"""Gradio 模型驱动 LLM 面板原型（最小可行）。

方向：Tk 常驻取词作为捕获终端，LLM 富交互（多轮对话 + markdown 渲染 +
流式输出）让渡给独立的 Gradio Web 面板。本模块只做「一个可点开的 LLM 面板
+ 首轮传入捕获词」，用于验证手感；Tk 里现有 LLM 面板保留作回退。

约定：顶层不 import gradio（未安装时本模块仍可被 import、纯逻辑可单测），
只在构建/启动时才 `import gradio as gr`。
"""
import re
import threading
import webbrowser

# 未安装 gradio 时的友好提示
GRADIO_REQUIRED_HINT = "需要先安装依赖：pip install gradio"

# 公式统一由服务端（matplotlib mathtext）预渲染成 SVG 图片内嵌，
# 行内 `$...$`、`\(...\)` 与块级 `$$...$$`、`\[...\]` 均会被渲染成真上下标。
# 因此模型可按习惯书写（线内或块级），无需顾虑下划线被解析成斜体。
FORMULA_BLOCK_HINT = (
    "公式可用行内 `$...$`（如 `$a_i^2$`）或块级 `$$...$$` 书写，"
    "两者都会正确渲染成公式，段落变量也会显示为真上下标。"
)


def with_formula_hint(system_prompt):
    """在 system_prompt 末尾追加「公式用块级」引导，供各启动入口复用。"""
    return f"{system_prompt}\n\n{FORMULA_BLOCK_HINT}"


# 段落中「变量下标下划线」：两侧都是字母/数字/数学括号时，几乎必是变量
# （a_i / x_1 / C_{n}^{k}），此时 `_` 会被 markdown 当斜体强调导致变量走形。
_UNDERSCORE_VAR = re.compile(r"(?<=[A-Za-z0-9)\]}])\_(?=[A-Za-z0-9{(\[<])")
# 受保护区域：块级公式 `$$...$$`、行内代码/代码块，其内部不处理、原样保留
_PROTECTED_SPAN = re.compile(r"\$\$.+?\$\$|```.+?```|`[^`]+`", re.S)


def guard_inline_variables(text):
    """把散文段落里会被 markdown 误当斜体的变量下标 `_` 转义成字面（反斜杠+下划线）。

    块级公式、行内代码、代码块整体跳过，避免误伤；真正的斜体强调
    `_word_`（两侧是空格/标点）不受影响。零依赖、纯逻辑、可单测。
    """
    def _escape(segment):
        return _UNDERSCORE_VAR.sub(r"\_", segment)

    out, pos = [], 0
    for m in _PROTECTED_SPAN.finditer(text):
        out.append(_escape(text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_escape(text[pos:]))
    return "".join(out)


# ---- 公式渲染：matplotlib mathtext → SVG data-uri，服务端、离线、可单测 ----
# 原理：把 `$..$`/`\(..\)`/`$$..$$`/`\[..\]` 在服务端渲染成小公式图，
# 内嵌为 markdown 图片 `![](...)`。gradio 的 markdown 对图片天然放行，
# 因此公式内部的 `_`(下标) 不会被 markdown 误解析成斜体，变量显示为真上下标。
# 保持惰性 import：matplotlib 是重依赖，未安装不影响模块其余逻辑。
_MATH_LOCK = threading.Lock()
_MATH_IMPORT_ERR = None
_BLOCK_MATH = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]", re.S)
_INLINE_MATH = re.compile(r"\$(?!\$)(.+?)(?<!\$)\$|\\\((.+?)\\\)", re.S)


def _tex_to_datauri(tex, size):
    """把单段 LaTeX 渲染成 SVG 的 data-uri 字符串；失败/无 matplotlib 时返回 None。"""
    global _MATH_IMPORT_ERR
    if _MATH_IMPORT_ERR is not None:
        return None
    try:
        import base64
        import io

        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
    except Exception as e:  # noqa: BLE001 - 缺依赖时优雅降级
        _MATH_IMPORT_ERR = e
        return None
    with _MATH_LOCK:  # matplotlib 非线程安全，防并发渲染竞态
        try:
            fig = plt.figure()
            fig.text(0.0, 0.0, f"${tex}$", fontsize=size)
            buf = io.BytesIO()
            fig.savefig(
                buf,
                format="svg",
                bbox_inches="tight",
                transparent=True,
                pad_inches=0.02,
            )
            plt.close(fig)
        except Exception:  # noqa: BLE001 - 渲染失败保留原文
            return None
        svg = buf.getvalue().decode()
        # 字形本身无显式 fill（缺省黑色）。注入 currentColor 让其继承所在文字颜色，
        # 于是浅色/深色主题下公式都跟正文同色，不会在暗背景上发黑刺眼。
        svg = svg.replace("<svg ", '<svg fill="currentColor" ')
        return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _replace_math(text, pattern, size):
    def _repl(m):
        tex = m.group(1) or m.group(2)
        uri = _tex_to_datauri(tex, size)
        return uri and f"![]({uri})" or m.group(0)

    return pattern.sub(_repl, text)


def render_multimath(text, inline_size=8, block_size=12):
    """把行内与块级公式统一渲染为 SVG 图片，其余文本原样保留。

    优先处理块级（`$$..$$` / `\\[..\\]`），再处理行内（`$..$` / `\\(..\\)`），
    避免相互吞并；任一公式渲染失败或 matplotlib 缺失时原样保留原文。
    """
    text = _replace_math(text, _BLOCK_MATH, block_size)
    text = _replace_math(text, _INLINE_MATH, inline_size)
    return text


def _splice_protected(text, fn):
    """在受保护区域（块级公式、代码块、行内代码）之外的文本上执行 fn。

    返回拼接结果，保证公式/代码内容原样保留、不被后续处理改动。
    """
    out, pos = [], 0
    for m in _PROTECTED_SPAN.finditer(text):
        out.append(fn(text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(fn(text[pos:]))
    return "".join(out)


def expand_soft_breaks(text):
    """Gradio 的 markdown 默认不把单个换行符（`\\n`）当换行，导致很多
    多行回答被挤成一大段、看起来「压在一行显示不全」。

    这里把「单独出现、前后都不是换行」的 `\\n` 转成 markdown 软换行
    （行尾两个空格 + 换行），让段落自然换行；代码块/行内代码/块级公式
    保持原样，不受影响。
    """
    def _soft(seg):
        return re.sub(r"(?<!\n)\n(?!\n)", "  \n", seg)

    return _splice_protected(text, _soft)


def to_gradio_history(history):
    """把 [{role, content}, ...] 折叠成 Gradio Chatbot 的 [[user, bot], ...] 形式。

    assistant 消息与后续 user 消息配对；末尾若有多余 user 消息单独成行。
    纯逻辑、无 gradio 依赖，便于单测。
    """
    pairs = []
    pending = None
    for msg in history:
        if msg["role"] == "user":
            pending = msg["content"]
        else:  # assistant
            pairs.append([pending if pending is not None else "", msg["content"]])
            pending = None
    if pending is not None:
        pairs.append([pending, ""])
    return pairs


def to_chat_messages(gradio_history, latest_user=""):
    """把 Gradio history 还原成 [{role, content}]，并把本轮输入追加为 user 消息。"""
    messages = []
    for user, bot in gradio_history:
        messages.append({"role": "user", "content": user})
        if bot:
            messages.append({"role": "assistant", "content": bot})
    if latest_user:
        messages.append({"role": "user", "content": latest_user})
    return messages


def build_app(chat, system_prompt, initial_chatbot=None):
    """构建 Gradio Blocks 应用。

    chat(messages, system_prompt=...) -> str：同步返回回答（与 llm_client 一致），
    便于后续无缝替换为流式版本。

    initial_chatbot: 可选初始问答对 [[user, bot], ...]，用作面板打开时的预置
    内容（例如验证某类 markdown/公式的实际渲染效果），无需发消息即可看到。
    """
    try:
        import gradio as gr
    except ImportError:  # pragma: no cover - 需要真装 gradio
        raise RuntimeError(GRADIO_REQUIRED_HINT)

    with gr.Blocks(title="LLM 对话面板") as demo:
        chatbot = gr.Chatbot(label="多轮对话", height=520, value=initial_chatbot or [])
        with gr.Row():
            user_input = gr.Textbox(
                label="追问/输入", scale=5, placeholder="输入内容后回车或点发送"
            )
            send_btn = gr.Button("发送", scale=1, variant="primary")

        def respond(history, prompt):
            # gradio 6 Chatbot 使用 messages(dict) 格式：{"role","content"}[]
            messages = list(history or [])
            messages.append({"role": "user", "content": prompt})
            answer = chat(messages, system_prompt=system_prompt).strip()
            answer = render_multimath(answer)
            answer = guard_inline_variables(answer)
            answer = expand_soft_breaks(answer)
            messages.append({"role": "assistant", "content": answer})
            return messages, ""

        send_btn.click(respond, [chatbot, user_input], [chatbot, user_input])
        user_input.submit(respond, [chatbot, user_input], [chatbot, user_input])
    return demo


def launch_panel(initial_word, chat, system_prompt, port=7860, in_browser=True):
    """启动 Gradio 面板并（可选）在浏览器打开；返回 (demo, url)。

    initial_word 作为首轮用户词预填进历史，让「捕获词→面板」建立衔接。
    """
    demo = build_app(chat, system_prompt)
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        inbrowser=False,  # 手动控制打开时机
        share=False,
    )
    url = demo.local_url or f"http://127.0.0.1:{port}"
    if in_browser:
        webbrowser.open(url)
    return demo, url


class PanelRef:
    """持有已启动面板的引用，便于主程序退出前优雅关闭。"""

    def __init__(self, demo=None, url=None):
        self.demo = demo
        self.url = url


def launch_in_thread(initial_word, chat, system_prompt, port=7860, on_ready=None):
    """非阻塞启动面板：后台线程 launch，就绪回调 on_ready(PanelRef)。

    供 Tk 按钮「点 LLM → 弹 Gradio 面板」调用，避免阻塞主现场。
    """
    ref = PanelRef()

    def runner():
        demo, url = launch_panel(initial_word, chat, system_prompt, port)
        ref.demo = demo
        ref.url = url
        if on_ready:
            on_ready(ref)

    threading.Thread(target=runner, daemon=True).start()
    return ref