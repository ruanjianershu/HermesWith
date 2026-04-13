# Track A1: AgentRuntime Core - 详细任务

## 目标
完善 AgentRuntime，支持 Tool Registry 加载和记忆系统集成。

## 当前状态
- `agent_runtime.py` 已有基础框架
- `_execute_with_hermes()` 能调用 LLM
- 但 Tool Registry 未加载，记忆系统未接入

## 任务清单

### 1. Tool Registry 集成
```python
# 在 AgentRuntime._init_hermes_agent() 中
# 确保 toolsets 参数真正生效

# 需要修复：当前 toolsets 传给 AIAgent 但可能未正确加载
# 需要调用 model_tools._discover_tools() 来实际注册工具
```

### 2. 记忆系统集成
```python
# 创建 hermeswith/runtime/memory_adapter.py
# 包装 Hermes 的 memory 系统，添加 PostgreSQL 后端

class PersistentMemory:
    def recall(self, query: str, limit: int = 5) -> List[Memory]
    def save(self, key: str, value: Any, importance: float = 0.5)
```

### 3. 运行时专属工具
创建 `hermeswith/tools/runtime_tools.py`:
- `goal_complete` - 标记 Goal 完成
- `ask_user` - 向用户提问（通过 WebSocket）
- `delegate_to_agent` - 委托给另一个 Agent

### 4. 系统提示词增强
在 `_build_system_prompt()` 中加入：
- Agent 角色定义
- 可用工具列表
- 行为准则

## 验收标准
```bash
cd /Users/liting/workspace/hermeswith
export KIMI_API_KEY=...

# 验证工具加载
python -c "
from hermeswith.runtime import AgentConfig, AgentRuntime
config = AgentConfig(toolsets=['terminal', 'file'])
rt = AgentRuntime(config)
print('Tools loaded:', len(rt.agent.tool_registry) if rt._has_hermes else 'N/A')
"

# 验证带工具的 Goal 执行
python examples/verify_tools.py  # 需要创建这个测试文件
```
