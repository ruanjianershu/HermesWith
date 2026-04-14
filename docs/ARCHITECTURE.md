# HermesWith Architecture

This document describes the architecture, design decisions, and component interactions of the HermesWith platform.

---

## Table of Contents

1. [High-Level Design](#high-level-design)
2. [Control Plane](#control-plane)
3. [Agent Runtime](#agent-runtime)
4. [Persistent Memory](#persistent-memory)
5. [Goal Queue](#goal-queue)
6. [Communication Flows](#communication-flows)
7. [Data Model](#data-model)
8. [Security Model](#security-model)
9. [Scaling Considerations](#scaling-considerations)
10. [Future Roadmap](#future-roadmap)

---

## High-Level Design

HermesWith follows a **hub-and-spoke** architecture:

- **Control Plane** (hub): Central API, WebSocket hub, and persistence layer
- **Agent Runtimes** (spokes): Containerized workers that pull goals and execute them

This design enables:
- **Horizontal scaling** of agents independently
- **Real-time observability** via WebSockets
- **Clean separation** between orchestration and execution

```
                    ┌─────────────────┐
                    │   Web UI / CLI  │
                    └────────┬────────┘
                             │ HTTP / WS
                             ▼
                    ┌─────────────────┐
                    │  Control Plane  │
                    │   (FastAPI)     │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ Runtime #1  │   │ Runtime #2  │   │ Runtime #N  │
    │ researcher  │   │  developer  │   │   analyst   │
    └─────────────┘   └─────────────┘   └─────────────┘
```

---

## Control Plane

**File:** `hermeswith/control_plane/api.py`

The Control Plane is a FastAPI application that exposes:

### Responsibilities

1. **Goal Management API**
   - Create, read, list, and delete goals
   - Goals are persisted to PostgreSQL and pushed to Redis queues

2. **Agent Registry**
   - Track registered agent runtimes
   - Expose pause/resume controls
   - Support direct goal execution on registered agents

3. **WebSocket Hub**
   - `WS /ws/agents/{agent_id}`
   - Broadcasts agent progress to connected clients
   - Accepts user interventions (pause, resume, cancel, message)

4. **Connection Manager**
   - `ConnectionManager` maintains active WebSocket connections per agent
   - Handles disconnections gracefully

### Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.goal_queue = RedisGoalQueue(...)
    yield
    # cleanup
```

The lifespan context initializes the Redis goal queue on startup.

---

## Agent Runtime

**File:** `hermeswith/runtime/agent_runtime.py`

The `AgentRuntime` is the core execution engine. Each agent runs in its own process/container with:

### Components

| Component | Purpose |
|-----------|---------|
| `AIAgent` | Hermes reasoning engine |
| `PersistentMemory` | Long-term context store |
| `WSClient` | WebSocket connection to Control Plane |
| `InterventionQueue` | Async queue for user messages |

### Execution Loop

```python
async def run(self):
    while True:
        goal = await self._pull_goal()
        if goal:
            await self._execute_goal(goal)
        else:
            await asyncio.sleep(1)
```

### Goal Execution Flow

1. **Pull** goal from Redis queue
2. **Notify** WebSocket subscribers (`goal_started`)
3. **Build** system prompt with role + available tools
4. **Execute** via Hermes AIAgent (or mock fallback)
5. **Save** execution record
6. **Notify** completion or failure

### Pause / Resume

Agents can be paused via the Control Plane API. When paused:
- The main loop continues but `submit_goal()` raises `RuntimeError`
- Already-running goals continue to completion

### Mock Mode

If Hermes AIAgent is unavailable (e.g., during testing), the runtime falls back to a mock executor that simulates a 2-second delay and returns a mock result.

---

## Persistent Memory

**File:** `hermeswith/runtime/memory_adapter.py`

The `PersistentMemory` class provides a simple key-value store for agent context.

### Current Implementation

- **Backend:** In-memory `dict[str, Memory]`
- **Query:** Substring search over keys and values
- **Ranking:** Results sorted by `importance` (desc), then `created_at` (asc)

### Future Plans

- PostgreSQL backend for cross-session persistence
- PGVector integration for semantic memory search
- Automatic memory summarization and pruning

### Interface

```python
memory = PersistentMemory()
memory.save("user_preference", "dark_mode", importance=0.8)
results = memory.recall("preference", limit=5)
```

---

## Goal Queue

**File:** `hermeswith/control_plane/goal_queue.py`

`RedisGoalQueue` provides a Redis-backed FIFO queue for goals with an in-memory fallback for local development and testing.

### Operations

| Method | Description |
|--------|-------------|
| `push(agent_id, goal)` | Add goal to agent's queue |
| `pull(agent_id, timeout)` | Blocking pop of next goal |
| `list_pending(agent_id)` | List all queued goals |
| `remove(agent_id, goal_id)` | Remove specific goal by ID |

### Fallback Mode

When Redis is unavailable, the queue transparently falls back to an `asyncio.Lock`-protected dictionary:

```python
self._fallback: Dict[str, List[Goal]] = {}
```

This ensures the system works out-of-the-box without infrastructure dependencies.

---

## Communication Flows

### 1. Submit Goal via API

```
User ──► Control Plane ──► PostgreSQL (save)
              │
              ▼
         Redis Queue (push)
              │
              ▼
    Agent Runtime (pull + execute)
              │
              ▼
         WebSocket (notify)
              │
              ▼
            User UI
```

### 2. Direct Execution

```
User ──► Control Plane ──► Agent Runtime (submit_goal)
                              │
                              ▼
                         Hermes AIAgent
                              │
                              ▼
                    PostgreSQL (save result)
```

### 3. User Intervention

```
User UI ──► WebSocket ──► Control Plane ──► WebSocket ──► Agent Runtime
                                                         (InterventionQueue)
```

---

## Data Model

### Goal

```python
class Goal(BaseModel):
    id: str                # UUID
    agent_id: str          # Assigned agent
    company_id: str        # Tenant
    description: str       # Natural language objective
    context: dict          # Additional constraints/data
    status: str            # pending | planning | executing | completed | failed
    created_at: datetime
```

### GoalExecution

```python
class GoalExecution(BaseModel):
    goal_id: str
    agent_id: str
    started_at: datetime | None
    completed_at: datetime | None
    trajectory: list       # LLM message history
    final_output: str
    tool_calls: list
    token_usage: int
    status: str
    error: str | None
```

### Database Schema (SQLAlchemy)

- **`goals`** — stores `Goal` records
- **`goal_executions`** — stores execution results and trajectories
- **`agent_memories`** — stores persistent memory entries

All JSON fields use PostgreSQL `JSONB` for efficient querying.

---

## Security Model

### Current (MVP)

- Agents run in isolated Docker containers
- Code execution is sandboxed within the runtime environment
- No authentication layer yet (planned)

### Planned

- API key authentication on Control Plane
- mTLS between Control Plane and Agent Runtimes
- Role-based access control (RBAC) per company_id
- Secret injection via environment variables only

---

## Scaling Considerations

| Concern | Strategy |
|---------|----------|
| **Agent scaling** | Each agent is a separate container; scale horizontally |
| **Queue scaling** | Redis handles queue distribution; can shard by agent_id |
| **DB scaling** | Read replicas for goal listings; connection pooling |
| **WebSocket scaling** | Sticky sessions or shared Redis Pub/Sub for WS hub |
| **Memory scaling** | PGVector for semantic search; tiered hot/warm storage |

---

## Future Roadmap

1. **Authentication & Authorization**
   - API keys, company-level isolation, RBAC

2. **Persistent Memory v2**
   - PostgreSQL backend, semantic search, memory consolidation

3. **Multi-Agent Orchestration**
   - Agent-to-agent delegation with dependency tracking
   - Workflow DAGs for complex multi-step processes

4. **Observability**
   - Structured logging, tracing, metrics export
   - Real-time execution viewer in Web UI

5. **Tool Marketplace**
   - Pluggable toolsets, third-party integrations
   - Dynamic tool discovery and registration

6. **Human-in-the-Loop**
   - Approval gates, review checkpoints, feedback loops

---

## See Also

- [README.md](../README.md) — Quick start and API reference
- `hermeswith/control_plane/api.py` — Control Plane implementation
- `hermeswith/runtime/agent_runtime.py` — Runtime implementation
- `hermeswith/runtime/memory_adapter.py` — Memory adapter
- `hermeswith/control_plane/goal_queue.py` — Goal queue implementation
