# Track D: Persistence Layer

## 目标
创建 PostgreSQL 持久化层，实现 Goal 和执行记录的持久化存储。

## 任务清单

### 1. 数据库连接
创建 `hermeswith/persistence/database.py`:
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base

Base = declarative_base()

async def init_db()
async def get_session() -> AsyncSession
```

### 2. SQLAlchemy Models
创建 `hermeswith/persistence/models.py`:
```python
class GoalDB(Base):
    __tablename__ = "goals"
    id = Column(UUID, primary_key=True)
    agent_id = Column(String, index=True)
    company_id = Column(String, index=True)
    description = Column(Text)
    context = Column(JSONB)
    status = Column(String, default="pending")
    created_at = Column(DateTime)

class GoalExecutionDB(Base):
    __tablename__ = "goal_executions"
    id = Column(UUID, primary_key=True)
    goal_id = Column(UUID, ForeignKey("goals.id"))
    agent_id = Column(String)
    status = Column(String)
    final_output = Column(Text)
    trajectory = Column(JSONB)
    tool_calls = Column(JSONB)
    token_usage = Column(Integer)
    created_at = Column(DateTime)
    completed_at = Column(DateTime)

class AgentMemoryDB(Base):
    __tablename__ = "agent_memories"
    id = Column(UUID, primary_key=True)
    agent_id = Column(String, index=True)
    memory_type = Column(String)
    key = Column(String)
    value = Column(Text)
    importance = Column(Float)
    # embedding = Column(Vector(1536))  # 可选，MVP 可以先不加
```

### 3. 数据库迁移
- 创建 `hermeswith/persistence/migrate.py`
- 使用 `asyncpg` 建表
- 启动 `docker-compose up -d postgres` 并执行迁移

### 4. 替换内存存储
修改 `control_plane/api.py`，用数据库读写替换 `app.state.goals` 字典。

## 验收标准
```bash
cd /Users/liting/workspace/hermeswith
docker-compose up -d postgres
python -m hermeswith.persistence.migrate
python -c "
import asyncio
from hermeswith.persistence.database import init_db
asyncio.run(init_db())
print('DB OK')
"
```
