# HermesWith

Multi-tenant Control Plane for Clawith - Enterprise-grade agent management, task scheduling, and tenant isolation API layer.

## 🎯 What is HermesWith?

HermesWith is a **multi-tenant Control Plane for Clawith**, providing enterprises with a unified API layer for agent management.

### Why HermesWith?

While Clawith is an excellent agent platform, enterprises face challenges when using it:

| Challenge | HermesWith Solution |
|-----------|-------------------|
| Multiple teams sharing Clawith without data isolation | Company-level multi-tenant isolation |
| No audit trail of who did what | Complete API audit logging |
| Coarse-grained permission control | Fine-grained API Key based permissions |
| Complex integration for internal systems | Standardized REST API |

## ✨ Features

- **🏢 Multi-tenant Architecture** - Company-level data isolation with API Key authentication
- **🤖 Agent Management** - Full lifecycle management of Clawith agents
- **📋 Task Scheduling** - Priority task queue with status tracking and output
- **🔒 Enterprise Security** - Fernet encryption for sensitive data, complete audit logs
- **⚡ Performance** - Redis rate limiting, async database operations

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│      Enterprise Internal Systems        │
│  (ERP / OA / Business Apps / Others)    │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         HermesWith (Control Plane)      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │ Multi-  │ │  Audit  │ │  Access │ │
│  │ tenant  │ │  Logger │ │ Control │ │
│  │ Manager │ │         │ │         │ │
│  └─────────┘ └─────────┘ └─────────┘ │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         Clawith (Agent Platform)        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │  Agent  │ │  Task   │ │ Output  │ │
│  │  Engine │ │ Executor│ │ Manager │ │
│  └─────────┘ └─────────┘ └─────────┘ │
└─────────────────────────────────────────┘
```

**HermesWith is not a modification of Clawith, but a management layer built on top of it.**

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# Create company and API Key
docker-compose exec api python -m hermeswith.cli create-company "My Company"
docker-compose exec api python -m hermeswith.cli create-api-key <company-id>
```

### Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env file with your Clawith configuration

# Initialize database
python -m hermeswith.cli init-db

# Create company and API Key
python -m hermeswith.cli create-company "My Company"
python -m hermeswith.cli create-api-key <company-id>

# Start server
uvicorn hermeswith.main:app --host 0.0.0.0 --port 8000 --reload
```

## 📡 API Endpoints

### Health Check
```
GET /health
```

### Agent Management (Proxy to Clawith)
```
POST   /v1/agents              # Create agent in Clawith
GET    /v1/agents              # List company agents
GET    /v1/agents/{id}         # Get agent details
PUT    /v1/agents/{id}         # Update agent
DELETE /v1/agents/{id}         # Delete agent
```

### Task Management (Proxy to Clawith)
```
POST   /v1/agents/{id}/tasks   # Assign task to agent
GET    /v1/tasks/{id}          # Get task status
GET    /v1/tasks/{id}/output   # Get task output
```

## 🔐 Authentication

### API Key Authentication (Recommended)
```http
X-API-Key: hw_xxxxxxxxxxxxxxxx
```

### JWT Bearer Token
```http
Authorization: Bearer <jwt-token>
```

## 📁 Project Structure

```
hermeswith/
├── api/                    # FastAPI routes and middleware
├── persistence/            # Database layer
├── security/               # Auth, encryption, rate limiting, audit
├── integrations/           # Clawith client and sync service
├── services/               # Business logic services
├── cli.py                  # CLI commands
├── config.py               # Configuration
└── main.py                 # Application entry
```

## 🔧 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/hermeswith` |
| `CLAWITH_BASE_URL` | Clawith API URL | `http://localhost:3000` |
| `CLAWITH_API_KEY` | Clawith API key | - |
| `REDIS_URL` | Redis URL | `redis://localhost:6379` |
| `RATE_LIMIT_PER_MINUTE` | Rate limit per minute | `60` |

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Create Pull Request


## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">Made with ❤️ for Clawith Enterprise Users</p>
