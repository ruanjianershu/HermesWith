# HermesWith 开发任务分配

> **前置要求**: Claude Code 已配置 kimi2.5
> **项目目录**: `/Users/liting/workspace/hermeswith`
> **上游代码**: `vendor/hermes-agent/` (symlink to `/Users/liting/.hermes/hermes-agent`)

---

## 快速启动 Claude Code（已配置 kimi2.5）

```bash
# 方式1：加载环境变量后启动
cd /Users/liting/workspace/hermeswith
export $(grep "^KIMI_API_KEY=" ~/.hermes/.env | xargs)
export ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
export ANTHROPIC_API_KEY=$KIMI_API_KEY
claude --acp --stdio

# 方式2：使用 wrapper 脚本
bash /Users/liting/workspace/start-hermeswith-dev.sh
```

---

## Track A1: AgentRuntime Core（核心运行时）

**目标**: 让 `AgentRuntime` 能真正调用 Hermes 的 `AIAgent`

**当前状态**: `hermeswith/runtime/agent_runtime.py` 已有框架，但 `_execute_with_hermes` 是 placeholder

**任务清单**:
- [ ] 分析 `vendor/hermes-agent/run_agent.py` 中 `AIAgent` 的构造函数和 `run_conversation` 方法签名
- [ ] 修复 `AgentRuntime` 中对 `run_conversation` 的调用方式（它可能是同步的）
- [ ] 将 `agent.chat()` 作为 fallback 路径加入
- [ ] 在 `AgentRuntime` 中集成 `tool_registry` 的加载（调用 `model_tools.py` 的 `_discover_tools()`）
- [ ] 测试：运行 `python examples/mvp_demo.py` 时，如果有 Hermes 依赖，应该能看到真实 LLM 调用

**验收标准**:
```bash
cd /Users/liting/workspace/hermeswith
python -c "
import sys
sys.path.insert(0, 'vendor/hermes-agent')
from hermeswith.runtime import AgentConfig, AgentRuntime
config = AgentConfig(agent_id='test', model='anthropic/claude-3-5-sonnet-20241022')
rt = AgentRuntime(config)
print('AIAgent loaded:', rt._has_hermes)
"
```

---

## Track A2: Runtime Config & Dependencies（运行时配置与依赖）

**目标**: 让项目能正确安装和运行

**任务清单**:
- [ ] 检查 `vendor/hermes-agent` 的依赖（requirements.txt, pyproject.toml）
- [ ] 将必要的依赖合并到 `/Users/liting/workspace/hermeswith/pyproject.toml`
- [ ] 测试 `pip install -e /Users/liting/workspace/hermeswith` 能成功
- [ ] 将 `AgentConfig.from_env()` 扩展：支持从 `.env` 文件加载
- [ ] 修改 `Dockerfile.runtime`，确保在容器内 `vendor/hermes-agent` 可用且 `PYTHONPATH` 正确

**验收标准**:
```bash
cd /Users/liting/workspace/hermeswith
pip install -e .
python -c "import hermeswith.runtime; print('OK')"
```

---

## Track B: Control Plane API（控制平面）

**目标**: 让 API 可以创建 Goal、查询状态、直接触发执行

**任务清单**:
- [ ] 完善 `hermeswith/control_plane/api.py`
- [ ] 实现 `POST /api/companies/{company_id}/goals` → 创建 Goal 并存入内存/Redis
- [ ] 实现 `GET /api/goals/{goal_id}` → 查询 Goal 状态
- [ ] 实现 `POST /api/agents/{agent_id}/execute` → 直接注册 AgentRuntime 并执行 Goal
- [ ] 添加基本的错误处理和日志

**验收标准**:
```bash
cd /Users/liting/workspace/hermeswith
uvicorn hermeswith.control_plane.api:create_app --reload &

# 在另一个终端
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/companies/demo/goals \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"test-agent","description":"test goal"}'
```

---

## Track C: WebSocket Hub（实时通信）

**目标**: Agent 执行进度能实时推送到客户端

**任务清单**:
- [ ] 在 `AgentRuntime` 中集成 `WebSocketManager`
- [ ] 实现 `AgentRuntime._notify()` 方法，向 `/ws/agents/{agent_id}` 广播进度消息
- [ ] 定义消息协议：`goal_started`, `step_progress`, `tool_call`, `goal_completed`, `goal_failed`
- [ ] 写一个 `examples/test_websocket.py` 客户端 Demo，连接 WS 并打印消息

**验收标准**:
```bash
# 1. 启动控制平面
uvicorn hermeswith.control_plane.api:create_app --reload

# 2. 运行 WS 测试客户端
python examples/test_websocket.py

# 3. 触发 Goal 执行，观察 WS 收到消息
```

---

## Track D: Persistence Layer（持久化层）

**目标**: Goal 和执行记录持久化到 PostgreSQL

**任务清单**:
- [ ] 创建 `hermeswith/persistence/database.py`（SQLAlchemy async 连接）
- [ ] 创建 SQLAlchemy models: `GoalDB`, `GoalExecutionDB`
- [ ] 将 `control_plane/api.py` 中的内存存储替换为数据库读写
- [ ] 启动 `docker-compose up postgres`，验证连接

**验收标准**:
```bash
cd /Users/liting/workspace/hermeswith
docker-compose up -d postgres
python -c "
import asyncio
from hermeswith.persistence.database import init_db
asyncio.run(init_db())
print('DB OK')
"
```

---

## Track E: Tool Integration（工具集成）

**目标**: AgentRuntime 能调用 Hermes 的工具

**任务清单**:
- [ ] 在 `vendor/hermes-agent` 中找出 `model_tools.py` 的 `_discover_tools()` 调用方式
- [ ] 在 `AgentRuntime._init_hermes_agent()` 中正确加载 toolsets
- [ ] 为 `AgentRuntime` 注册专属工具：`goal_complete`、`ask_user`
- [ ] 测试 Agent 在对话中调用 `web_search` 或 `file_write`

**验收标准**:
```bash
python -c "
from hermeswith.runtime import AgentConfig, AgentRuntime
config = AgentConfig(toolsets=['terminal', 'file'])
rt = AgentRuntime(config)
print('Available tools:', len(rt.agent.tool_registry) if rt._has_hermes else 'N/A')
"
```

---

## Track F: MVP Integration & Demo（MVP 联调与演示）

**目标**: 端到端跑通一个完整的 Goal 执行

**任务清单**:
- [ ] 整合 Track A-E 的成果
- [ ] 修复接口不匹配问题
- [ ] 完善 `examples/mvp_demo.py`，增加真实 LLM 调用路径
- [ ] 运行完整的 MVP Demo 并录屏/截图
- [ ] 更新 README.md 中的快速开始指南

**验收标准**:
```bash
cd /Users/liting/workspace/hermeswith
# 1. 启动基础设施
docker-compose up -d postgres redis

# 2. 启动控制平面
uvicorn hermeswith.control_plane.api:create_app --reload &

# 3. 运行 MVP Demo
python examples/mvp_demo.py
# 预期：看到 Goal 创建 → Agent 执行 → 返回结果
```

---

## 并行启动命令

```bash
# Terminal 1 - Track A1
export $(grep "^KIMI_API_KEY=" ~/.hermes/.env | xargs)
export ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
export ANTHROPIC_API_KEY=$KIMI_API_KEY
cd /Users/liting/workspace/hermeswith
claude --acp --stdio
# 任务：完成 Track A1 AgentRuntime Core

# Terminal 2 - Track A2
export $(grep "^KIMI_API_KEY=" ~/.hermes/.env | xargs)
export ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
export ANTHROPIC_API_KEY=$KIMI_API_KEY
cd /Users/liting/workspace/hermeswith
claude --acp --stdio
# 任务：完成 Track A2 Runtime Config & Dependencies

# Terminal 3 - Track B
export $(grep "^KIMI_API_KEY=" ~/.hermes/.env | xargs)
export ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
export ANTHROPIC_API_KEY=$KIMI_API_KEY
cd /Users/liting/workspace/hermeswith
claude --acp --stdio
# 任务：完成 Track B Control Plane API

# Terminal 4 - Track C
export $(grep "^KIMI_API_KEY=" ~/.hermes/.env | xargs)
export ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
export ANTHROPIC_API_KEY=$KIMI_API_KEY
cd /Users/liting/workspace/hermeswith
claude --acp --stdio
# 任务：完成 Track C WebSocket Hub

# Terminal 5 - Track D
export $(grep "^KIMI_API_KEY=" ~/.hermes/.env | xargs)
export ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
export ANTHROPIC_API_KEY=$KIMI_API_KEY
cd /Users/liting/workspace/hermeswith
claude --acp --stdio
# 任务：完成 Track D Persistence Layer

# Terminal 6 - Track E
export $(grep "^KIMI_API_KEY=" ~/.hermes/.env | xargs)
export ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
export ANTHROPIC_API_KEY=$KIMI_API_KEY
cd /Users/liting/workspace/hermeswith
claude --acp --stdio
# 任务：完成 Track E Tool Integration
```

---

**准备好后，直接复制对应的 Terminal 命令到各个窗口中启动。**
