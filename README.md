# HermesWith

**Enterprise AI Agent Platform**

HermesWith is a production-ready platform for deploying autonomous AI agents that execute goals, delegate tasks, and collaborate in real-time.

---

## Overview

HermesWith enables organizations to deploy persistent digital employees that:
- **Execute Goals**: Autonomously complete assigned tasks using available tools
- **Collaborate**: Work together via WebSocket real-time communication
- **Scale**: Run multiple agents in containerized environments
- **Observe**: Full visibility into agent execution via Control Plane API

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     HermesWith Platform                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────┐         ┌───────────────┐                    │
│  │ Control Plane │◄───────►│   PostgreSQL  │                    │
│  │   (FastAPI)   │         │   + Redis     │                    │
│  │               │         │               │                    │
│  │ • Goal API    │         │ • Goals       │                    │
│  │ • Agent Mgmt  │         │ • Executions  │                    │
│  │ • WebSocket   │         │ • Memory      │                    │
│  └───────┬───────┘         └───────────────┘                    │
│          │                                                      │
│          ▼                                                      │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐   │
│  │ Agent Runtime │    │ Agent Runtime │    │ Agent Runtime │   │
│  │  (Container)  │    │  (Container)  │    │     (N)       │   │
│  │               │    │               │    │               │   │
│  │ • AI Agent    │    │ • AI Agent    │    │ • ...         │   │
│  │ • Memory      │    │ • Memory      │    │               │   │
│  │ • Tools       │    │ • Tools       │    │               │   │
│  └───────────────┘    └───────────────┘    └───────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- PostgreSQL 14+ (or use Docker Compose)
- Redis (or use Docker Compose)

### Installation

```bash
git clone https://github.com/ruanjianershu/HermesWith.git
cd HermesWith
pip install -e ".[dev]"
```

### Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
```bash
AGENT_API_KEY=your-api-key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/hermeswith
REDIS_URL=redis://localhost:6379/0
```

### Start Services

```bash
# Start infrastructure
docker-compose up -d postgres redis

# Initialize database
python -c "import asyncio; from hermeswith.persistence.database import init_db; asyncio.run(init_db())"

# Start Control Plane
uvicorn hermeswith.control_plane.api:create_app --reload
```

### Submit Your First Goal

```bash
curl -X POST http://localhost:8000/api/companies/demo/goals \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-001",
    "description": "Research and summarize Python 3.13 features",
    "context": {"format": "markdown"}
  }'
```

---

## API Reference

### Health Check
```
GET /health
```

### Goals
```
POST   /api/companies/{company_id}/goals    # Create goal
GET    /api/goals/{goal_id}                  # Get goal
GET    /api/goals                            # List goals
DELETE /api/goals/{goal_id}                  # Delete goal
```

### Agents
```
GET    /api/agents                           # List agents
GET    /api/agents/{agent_id}                # Get agent status
POST   /api/agents/{agent_id}/register       # Register agent
POST   /api/agents/{agent_id}/pause          # Pause agent
POST   /api/agents/{agent_id}/resume         # Resume agent
POST   /api/agents/{agent_id}/execute        # Execute goal directly
```

### WebSocket
```
WS /ws/agents/{agent_id}
```

Real-time updates and interventions.

---

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# End-to-end tests
pytest tests/e2e/ -v
```

### Code Quality

```bash
black hermeswith/ tests/
ruff check hermeswith/ tests/
```

---

## Project Structure

```
hermeswith/
├── hermeswith/
│   ├── control_plane/      # FastAPI API and WebSocket hub
│   ├── persistence/        # Database models and migrations
│   ├── runtime/            # Agent execution environment
│   └── tools/              # Runtime tools
├── tests/
│   ├── unit/               # Unit tests
│   ├── integration/        # API integration tests
│   └── e2e/                # End-to-end tests
├── examples/               # Example scripts
├── docs/                   # Documentation
└── docker-compose.yml      # Infrastructure services
```

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Support

For issues and feature requests, please use GitHub Issues.
