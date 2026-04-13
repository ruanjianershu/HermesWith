# Track B: Control Plane API

## 目标
完善 FastAPI 控制平面，实现完整的 Goal CRUD 和 Agent 管理。

## 任务清单

### 1. Goal API 完整化
```python
# 当前是内存存储，需要：
- POST /api/companies/{company_id}/goals - 创建 Goal，推送到 Redis
- GET /api/goals/{goal_id} - 查询 Goal 详情（含执行状态）
- GET /api/goals?agent_id=xxx - 列出 Agent 的 Goals
- DELETE /api/goals/{goal_id} - 取消/删除 Goal
```

### 2. Agent 管理 API
```python
# 新增端点：
- GET /api/agents - 列出所有 Agents
- GET /api/agents/{agent_id} - 获取 Agent 详情
- POST /api/agents/{agent_id}/pause - 暂停 Agent
- POST /api/agents/{agent_id}/resume - 恢复 Agent
```

### 3. Redis 队列集成
创建 `hermeswith/control_plane/goal_queue.py`:
```python
class RedisGoalQueue:
    async def push(self, agent_id: str, goal: Goal)
    async def pull(self, agent_id: str) -> Optional[Goal]
    async def list_pending(self, agent_id: str) -> List[Goal]
```

### 4. API 文档
- 添加 FastAPI 自动文档支持
- 访问 `/docs` 能看到完整的 API 文档

## 验收标准
```bash
# 启动控制平面
uvicorn hermeswith.control_plane.api:create_app --reload

# 测试所有端点
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/companies/demo/goals \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"test","description":"test"}'
```
