#!/usr/bin/env bash
# 环境启动脚本：优先使用项目内置的 .venv 虚拟环境运行应用，
# 避免系统多 Python 版本下依赖缺失（如 python-xlib 导致
# _ensure_window_sticky 报 "No module named 'Xlib'"）。
#
# 用法:
#   ./run.sh                启动 Tk 取词桌面版（取词浮窗 + 翻译结果弹窗，默认）
#   ./run.sh --tk           等价于 ./run.sh
#   ./run.sh --gradio [词]  启动 Gradio 模型面板（网页，显式指定才启用）

set -euo pipefail
cd "$(dirname "$0")"

# 优先使用项目内置虚拟环境；缺失时回退到 ~/compiler/venv
if [ -x ".venv/bin/python3" ]; then
  VENV_PY="$(pwd)/.venv/bin/python3"
else
  VENV_PY="$HOME/compiler/venv/bin/python3"
fi

if [ ! -x "$VENV_PY" ]; then
  echo "❌ 未找到虚拟环境解释器: $VENV_PY。请确认 .venv 已创建。" >&2
  echo "   创建方式: python -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

# 加载必要环境变量（AGENTS.md 要求：任何依赖 env.sh 的命令必须先 source）
if [ -f env.sh ]; then
  # shellcheck source=/dev/null
  source env.sh
else
  echo "⚠️  缺少 env.sh，跳过环境变量加载（Gradio 模式需要 LLM_API_KEY）" >&2
fi

FIRST_ARG="${1:-}"
MODE="tk"

case "$FIRST_ARG" in
  "")
    # 无参数：默认启动取词桌面版
    MODE="tk"
    ;;
  --tk)
    MODE="tk"
    ;;
  --gradio)
    MODE="gradio"
    ;;
  -*)
    echo "❌ 未知参数: $FIRST_ARG" >&2
    echo "用法: $0 [--tk | --gradio [词]]" >&2
    exit 1
    ;;
  *)
    # 形如 "word" 的裸词：解析为 --gradio <词>
    MODE="gradio"
    ;;
esac

# 按模式补齐依赖
install_deps() {
  echo "🔧 正在安装依赖..." >&2
  "$VENV_PY" -m pip install -r requirements.txt >&2
}

if [ "$MODE" = "tk" ]; then
  # Tk 桌面版
  if ! "$VENV_PY" -c "import Xlib" >/dev/null 2>&1; then
    install_deps
  fi
  echo "▶️  启动 Tk 桌面版，解释器: $VENV_PY ($("$VENV_PY" --version 2>&1))"
  exec "$VENV_PY" dictionary_gui.py
else
  # Gradio 面板（依赖 gradio + matplotlib，软依赖）
  if ! "$VENV_PY" -c "import gradio, matplotlib" >/dev/null 2>&1; then
    echo "🔧 Gradio 面板需要 gradio 与 matplotlib，正在安装..." >&2
    "$VENV_PY" -m pip install -r requirements.txt "gradio" "matplotlib" >&2
  fi

  # 从参数取首轮词：`./run.sh word`、`./run.sh --gradio word`
  WORD=""
  if [ -n "$FIRST_ARG" ] && [ "$FIRST_ARG" != "--gradio" ]; then
    WORD="$FIRST_ARG"
  elif [ "$MODE" = "gradio" ] && [ "$#" -ge 2 ]; then
    WORD="$2"
  fi

  echo "▶️  启动 Gradio 面板，解释器: $VENV_PY ($("$VENV_PY" --version 2>&1))"
  exec "$VENV_PY" scripts/run_gradio_panel.py "$WORD"
fi