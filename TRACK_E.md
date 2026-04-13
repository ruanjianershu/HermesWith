# Track E: Tool Integration

## 目标
接入 Hermes 的 Tool Registry，让 AgentRuntime 能调用 90+ 工具。

## 任务清单

### 1. 分析 Hermes 工具加载机制
```python
# vendor/hermes-agent/model_tools.py
# 找到 _discover_tools() 和 load_tools_for_platform()
# 理解 toolset 如何映射到 tools/*.py
```

### 2. 在 AgentRuntime 中正确加载工具
修改 `hermeswith/runtime/agent_runtime.py`:
```python
def _init_hermes_agent(self):
    # 确保 toolsets 真正生效
    # 调用 model_tools._discover_tools() 或等效逻辑
    # 让 AIAgent 的 tool_registry 包含实际工具
```

### 3. 运行时专属工具注册
创建 `hermeswith/tools/runtime_tools.py`:
```python
from tools.registry import registry

@registry.register_toolset("hermeswith-runtime")
def register_runtime_tools():
    registry.register(
        name="goal_complete",
        toolset="hermeswith-runtime",
        schema={...},
        handler=...,
    )
    registry.register(
        name="ask_user",
        toolset="hermeswith-runtime",
        schema={...},
        handler=...,
    )
```

### 4. 工具调用测试
创建 `examples/verify_tools.py`:
```python
# 测试 terminal_tool 或 web_search
# 让 Agent 执行一个需要工具的 Goal
```

### 5. 处理缺失依赖
某些工具可能需要额外 API Key（如 `BROWSERBASE_API_KEY`）：
- 优雅降级：找不到依赖时不注册该工具
- 打印警告信息

## 验收标准
```bash
cd /Users/liting/workspace/hermeswith
export KIMI_API_KEY=...

python -c "
from hermeswith.runtime import AgentConfig, AgentRuntime
config = AgentConfig(toolsets=['terminal', 'file'])
rt = AgentRuntime(config)
if rt._has_hermes:
    # 检查 tools 是否已加载
    print('Tool count:', len(rt.agent.tool_registry))
"

# 端到端测试
python examples/verify_tools.py
```
