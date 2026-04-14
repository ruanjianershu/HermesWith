# HermesWith

**Hermes Brain + OpenClaw Body = Autonomous Digital Workforce**

HermesWith is an autonomous agent platform that pairs the Hermes AI reasoning engine with a scalable, observable runtime. It enables companies to deploy persistent digital employees that can execute goals, delegate tasks, and collaborate in real-time.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Project Structure](#project-structure)
4. [API Documentation](#api-documentation)
5. [Development](#development)
6. [Testing](#testing)
7. [Configuration](#configuration)
8. [License](#license)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HermesWith Platform                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐         ┌─────────────────────┐                   │
│  │   Control Plane     │◄───────►│   PostgreSQL DB     │                   │
│  │   (FastAPI)         │         │   + Redis Queue     │                   │
│  │                     │         │                     │                   │
│  │  • Goal API         │         │  • goals            │                   │
│  │  • Agent Registry   │         │  • goal_executions  │                   │
│  │  • WebSocket Hub    │         │  • agent_memories   │                   │
│  │  • Real-time UI     │         │  • Redis streams    │                   │
│  └──────────┬──────────┘         └─────────────────────┘                   │
│             │                                                               │
│             │ WebSocket / HTTP                                              │
│             ▼                                                               │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────┐ │
│  │   Agent Runtime 1   │    │   Agent Runtime 2   │    │   Agent Runtime │ │
│  │   (Container)       │    │   (Container)       │    │   N             │ │
│  │                     │    │                     │    │                 │ │
│  │  • Hermes AIAgent   │    │  • Hermes AIAgent   │    │  • ...          │ │
│  │  • PersistentMemory │    │  • PersistentMemory │    │                 │ │
│  │  • Runtime Tools    │    │  • Runtime Tools    │    │                 │ │
│  │  • Docker Sandbox   │    │  • Docker Sandbox   │    │                 │ │
│  └─────────────────────┘    └─────────────────────┘    └─────────────────┘ │
│                                                                             │
│  Runtime Tools: goal_complete | ask_user | delegate_to_agent                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Description | Tech |
|-----------|-------------|------|
| **Control Plane** | REST API + WebSocket hub for managing goals and agents | FastAPI, Uvicorn |
| **Agent Runtime** | Containerized execution environment for each agent | Python, Docker |
| **Hermes AIAgent** | Core reasoning and tool-use engine | Hermes Agent |
| **Persistent Memory** | Long-term context storage for agents | PostgreSQL + PGVector |
| **Goal Queue** | Redis-backed queue for distributing goals | Redis |
| **Intervention Queue** | Real-time user messaging to running agents | Asyncio Queue |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- Redis (or use Docker Compose)
- PostgreSQL 14+ (or use Docker Compose)

### 1. Clone and Install

```bash
cd /Users/liting/workspace/hermeswith
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and connection strings
```

Example `.env`:

```bash
AGENT_ID=agent-001
COMPANY_ID=default
AGENT_MODEL=k2p5
AGENT_API_KEY=your-api-key
KIMI_API_KEY=your-api-key
DATABASE_URL=postgresql+asyncpg://hermeswith:hermeswith@localhost:5432/hermeswith
REDIS_URL=redis://localhost:6379/0
CONTROL_PLANE_WS=ws://localhost:8000/ws
```

### 3. Start Infrastructure

```bash
docker-compose up -d db redis
```

### 4. Initialize Database

```bash
python -c "import asyncio; from hermeswith.persistence.database import init_db; asyncio.run(init_db())"
```

### 5. Start Control Plane

```bash
uvicorn hermeswith.control_plane.api:create_app --reload --port 8000
```

### 6. Submit a Goal

```bash
curl -X POST http://localhost:8000/api/companies/demo/goals \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "researcher-001",
    "description": "Summarize the latest Python release notes",
    "context": {"format": "markdown"}
  }'
```

### 7. Run an Agent Locally

```bash
python -m hermeswith.runtime.main
```

---

## Project Structure

```
hermeswith/
├── hermeswith/
│   ├── __init__.py
│   ├── control_plane/
│   │   ├── api.py              # FastAPI app: goals, agents, websockets
│   │   └── goal_queue.py       # Redis-backed goal queue
│   ├── persistence/
│   │   ├── database.py         # SQLAlchemy async engine & sessions
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   └── migrate.py          # Database migrations
│   ├── runtime/
│   │   ├── agent_runtime.py    # AgentRuntime & AgentConfig
│   │   ├── memory_adapter.py   # PersistentMemory
│   │   ├── intervention.py     # InterventionQueue
│   │   ├── ws_client.py        # WebSocket client with reconnect
│   │   └── main.py             # Runtime entrypoint
│   └── tools/
│       ├── __init__.py
│       └── runtime_tools.py    # goal_complete, ask_user, delegate_to_agent
├── tests/
│   ├── unit/
│   │   ├── test_agent_runtime.py
│   │   └── test_memory_adapter.py
│   ├── integration/
│   │   └── test_goal_api.py
│   └── e2e/
│       └── test_mvp_demo.py
├── docs/
│   └── ARCHITECTURE.md
├── examples/
│   └── mvp_demo.py
├── vendor/
│   └── hermes-agent-copy/      # Hermes agent source
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## API Documentation

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |

**Response:**
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### Goals

#### Create Goal
`POST /api/companies/{company_id}/goals`

**Request:**
```json
{
  "agent_id": "researcher-001",
  "description": "Find and summarize Python 3.13 features",
  "context": {"format": "markdown"}
}
```

**Response:**
```json
{
  "id": "uuid",
  "agent_id": "researcher-001",
  "company_id": "demo",
  "description": "Find and summarize Python 3.13 features",
  "status": "pending",
  "created_at": "2024-01-15T10:30:00"
}
```

#### Get Goal
`GET /api/goals/{goal_id}`

#### List Goals
`GET /api/goals?agent_id={agent_id}&status={status}&skip=0&limit=100`

#### Delete Goal
`DELETE /api/goals/{goal_id}`

---

### Agents

#### List Agents
`GET /api/agents`

**Response:**
```json
[
  {
    "agent_id": "researcher-001",
    "registered": true,
    "paused": false,
    "role": "researcher",
    "company_id": "demo"
  }
]
```

#### Get Agent
`GET /api/agents/{agent_id}`

#### Register Agent
`POST /api/agents/{agent_id}/register`

#### Pause Agent
`POST /api/agents/{agent_id}/pause`

#### Resume Agent
`POST /api/agents/{agent_id}/resume`

#### Execute Goal Directly
`POST /api/agents/{agent_id}/execute`

Executes a goal immediately on the specified agent.

**Request:**
```json
{
  "agent_id": "researcher-001",
  "description": "Say hello",
  "context": {"test": true}
}
```

**Response:**
```json
{
  "goal_id": "uuid",
  "status": "completed",
  "output": "Hello!"
}
```

---

### WebSocket

`WS /ws/agents/{agent_id}`

Connect to receive real-time updates from an agent and send interventions.

**Intervention message:**
```json
{
  "type": "intervene",
  "message": "Please focus on performance metrics"
}
```

**Agent events:**
- `goal_started`
- `goal_completed`
- `goal_failed`
- `intervention_received`

---

## Development

### Code Style

```bash
black hermeswith/ tests/
ruff check hermeswith/ tests/
```

### Type Checking

```bash
mypy hermeswith/
```

---

## Testing

HermesWith uses **pytest** with three test tiers:

### Unit Tests

```bash
pytest tests/unit/ -v
```

Tests individual components in isolation:
- `test_agent_runtime.py` — `AgentRuntime`, `Goal`, `AgentConfig`
- `test_memory_adapter.py` — `PersistentMemory`, `Memory`

### Integration Tests

```bash
pytest tests/integration/ -v
```

Tests API endpoints with mocked external dependencies:
- `test_goal_api.py` — Goal CRUD, agent management, WebSockets

### End-to-End Tests

```bash
pytest tests/e2e/ -v
```

Tests full system flows:
- `test_mvp_demo.py` — Health, goal creation, direct execution, pause/resume, queue operations, WebSocket

### Run All Tests

```bash
pytest -v
```

---

## Configuration

All configuration is loaded from environment variables via `AgentConfig.from_env()`.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_ID` | `agent-001` | Unique agent identifier |
| `COMPANY_ID` | `default` | Company/tenant identifier |
| `AGENT_ROLE` | `assistant` | Agent role description |
| `AGENT_MODEL` | `k2p5` | LLM model name |
| `AGENT_BASE_URL` | `https://api.kimi.com/coding/v1` | LLM API base URL |
| `AGENT_API_KEY` | — | Primary API key |
| `KIMI_API_KEY` | — | Fallback API key |
| `AGENT_TOOLSETS` | `terminal,file` | Comma-separated toolset list |
| `AGENT_MAX_ITERATIONS` | `20` | Max agent reasoning steps |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `CONTROL_PLANE_WS` | `ws://localhost:8000/ws` | Control Plane WebSocket URL |
| `WORKSPACE_DIR` | `/workspace` | Agent workspace directory |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
