# AGENTS.md

## 项目规则

### 运行依赖 env.sh 环境变量的脚本

当需要执行依赖 `env.sh` 中环境变量的脚本时，**必须**使用以下方式加载环境变量后再执行：

```bash
bash -c 'source env.sh && python3 <script.py>'
```

绝对不要直接执行 `python3 script.py` 而不先 source env.sh，否则会因为缺少环境变量而报错。

### 执行涉及 LLM API 的命令

LLM API 调用天生慢（5-30秒），且可能因网络波动无限挂起。执行时**必须同时满足**以下三点：

1. **加 `timeout`** — 防止进程无限挂起
2. **用 `blocking=true`** — 不要用手动轮询等待（wait_ms_before_check），让工具自行监听进程退出信号
3. **正确加载 env.sh** — 参见上一条

**正确示例：**

```bash
bash -c 'source env.sh && timeout 60 python3 llm_client.py "你的prompt"'
```

**错误示例：**

```bash
# ❌ 没有 timeout，进程可能永远挂起
python3 llm_client.py "你的prompt"

# ❌ 用 blocking=false + 长轮询，进程可能早已退出但还在傻等
RunCommand(blocking=false, wait_ms_before_check=20000, ...)

# ❌ 忘记 source env.sh，会因为缺少 API Key 报错
bash -c 'timeout 60 python3 llm_client.py "你的prompt"'
```

### 项目依赖

- Python 3
- requests 库
- LLM API（需要 env.sh 中配置 API Key）

### 文件结构

- `llm_client.py` — 通用 LLM 客户端，提供 chat() 函数
- `env.sh` — 环境变量配置（LLM_API_KEY, LLM_BASE_URL, LLM_MODEL）