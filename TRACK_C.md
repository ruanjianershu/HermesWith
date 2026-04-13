# Track C: WebSocket Hub

## 目标
实现 WebSocket 实时进度推送，Agent 可以广播执行状态，客户端可以发送干预指令。

## 任务清单

### 1. AgentRuntime WebSocket 集成
修改 `hermeswith/runtime/agent_runtime.py`:
```python
class WSClient:
    async def connect(self, url: str)
    async def send(self, message: dict)

class AgentRuntime:
    async def _notify(self, message: str):
        """向 WebSocket 广播进度"""
```

### 2. 消息协议定义
定义标准消息格式：
```json
{"type": "goal_started", "goal_id": "...", "agent_id": "..."}
{"type": "step_progress", "content": "正在搜索新闻..."}
{"type": "tool_call", "tool": "web_search", "params": {...}}
{"type": "goal_completed", "output": "..."}
{"type": "goal_failed", "error": "..."}
{"type": "intervention_received", "message": "..."}
```

### 3. 用户干预机制
- WebSocket 客户端发送 `type: "intervene"` 消息
- `AgentRuntime` 接收并处理干预（如暂停、修改提示词）
- 创建 `hermeswith/runtime/intervention.py` 管理干预队列

### 4. 测试客户端
创建 `examples/test_websocket.py`:
```python
import websockets

async def listen():
    async with websockets.connect("ws://localhost:8000/ws/agents/test") as ws:
        ...
```

## 验收标准
```bash
# 启动控制平面
uvicorn hermeswith.control_plane.api:create_app --reload

# 运行 WS 测试
python examples/test_websocket.py
# 然后触发 Goal，观察消息流
```
