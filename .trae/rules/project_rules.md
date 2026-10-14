# 项目规则

> 本文为持久化规则，IDE 每次会话自动加载，用于弥补 AGENTS.md（GitLab 仓库级）不随 IDE 载入的问题。
> 与本仓库 `AGENTS.md` 不一致时以此要求为准执行。

## 命令执行规范（必守）

依赖 `env.sh` 环境变量、以及所有命令的发起方式，统一遵循以下三条。**不得省略、不得精简、不得因“节省步骤”而降级。**

### 1. 依赖 env.sh 的脚本：必须先 source

凡需 `env.sh` 中环境变量（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）的脚本，执行前**必须**加载环境变量：

```bash
bash -c 'source env.sh && python3 <script.py>'
```

必须禁止直接执行 `python3 script.py`（会因缺少环境变量报错）。`env.sh` 位于仓库根目录。

### 2. 涉及 LLM API 的命令：timeout + blocking=true + source env.sh

LLM 调用天然慢（5–30 秒），且可能因网络波动无限挂起。执行时**三条件必须同时满足**：

1. **加 `timeout`** —— 防止进程无限挂起
2. **`blocking=true`** —— 不要用手动轮询等待，让工具自行监听进程退出信号
3. **`source env.sh`** —— 见第 1 条

**正确：**
```bash
bash -c 'source env.sh && timeout 60 python3 services/llm_client.py "你的prompt"'
```

**错误：**
```bash
# ❌ 没有 timeout，可能永久挂起
python3 services/llm_client.py "你的prompt"
# ❌ blocking=false + 长轮询，进程可能已退出仍在傻等
RunCommand(blocking=false, wait_ms_before_check=20000, ...)
# ❌ 忘了 source env.sh，因缺少 API Key 报错
bash -c 'timeout 60 python3 services/llm_client.py "你的prompt"'
```

### 3. 命令输出获取：异步 + 限时轮询 + 重定向兜底

原因：控制台命令的**结果输出有时会丢失**。因此统一做法：

1. **异步执行** —— `RunCommand(blocking=false)` 启动，避免阻塞
2. **限时轮询** —— 有限次数内用 `CheckCommandStatus` 取结果，不让轮询无限持续
3. **重定向兜底** —— 输出始终取不到时，重定向到临时文件再读：

```bash
bash -c 'source env.sh && python3 services/llm_client.py "你的prompt" > /tmp/llm_out.txt 2>&1'
```

### 冲突裁量

- 第 2 条（LLM：`blocking=true` + timeout）与第 3 条（通用：`blocking=false` 异步）针对不同场景：**慢且必须等结果的 LLM 调用**用第 2 条；**快速/长时程命令的输出获取**用第 3 条异步 + 限时轮询 + 重定向。两者不可混用降级。

## 本仓库相关

- Python 3 + requests
- LLM 客户端：`services/llm_client.py`（提供 `chat()`）
- 环境变量：`env.sh`（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）