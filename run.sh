#!/usr/bin/env bash
# 环境启动脚本：使用 ~/compiler/venv 虚拟环境运行 GUI，
# 避免系统多 Python 版本下 python-xlib 缺失导致
# _ensure_window_sticky 报 "No module named 'Xlib'"。
# 用法: ./run.sh

set -euo pipefail
cd "$(dirname "$0")"

# 指定虚拟环境解释器
VENV_PY="$HOME/compiler/venv/bin/python3"

if [ ! -x "$VENV_PY" ]; then
  echo "❌ 未找到虚拟环境解释器: $VENV_PY。请确认 venv 已创建。" >&2
  exit 1
fi

# 加载必要环境变量（AGENTS.md 要求：任何依赖 env.sh 的命令必须先 source）
if [ -f env.sh ]; then
  # shellcheck source=/dev/null
  source env.sh
else
  echo "⚠️  缺少 env.sh，跳过环境变量加载" >&2
fi

# 确保 python-xlib 就绪
if ! "$VENV_PY" -c "import Xlib" >/dev/null 2>&1; then
  echo "🔧 虚拟环境缺少 python-xlib，正在安装依赖..." >&2
  "$VENV_PY" -m pip install -r requirements.txt >&2
fi

echo "▶️  使用解释器: $VENV_PY ($("$VENV_PY" --version 2>&1))"
exec "$VENV_PY" dictionary_gui.py