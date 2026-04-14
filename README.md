# HermesWith

Multi-tenant AI agent management platform for enterprises.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0+-orange.svg" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License">
</p>

## 🎯 What is HermesWith?

HermesWith is a multi-tenant AI agent management platform for enterprises, supporting creation, management, and monitoring of AI agents with automated task assignment and execution tracking.

### Core Capabilities

- **Multi-tenant Isolation** - Company-level data isolation with API Key authentication
- **Agent Lifecycle** - Create, configure, monitor, and delete agents
- **Task Scheduling** - Priority task queue with async execution and status tracking
- **Enterprise Security** - Fernet encryption, audit logging, rate limiting

## ✨ Features

- **🏢 Multi-tenant Architecture** - Company-based data isolation with API Key authentication
- **🤖 Agent Management** - Create, configure, and monitor AI agents
- **📋 Task Scheduling** - Priority task queue with status tracking and output
- **🔒 Enterprise Security** - Fernet encryption for sensitive data, complete audit logs
- **⚡ Performance** - Redis rate limiting, async database operations
- **🔍 Observability** - Detailed audit trails, rate limit monitoring

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│      Enterprise Internal Systems        │
│  (ERP / OA / Business Apps / Others)    │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         HermesWith Platform             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │ Multi-  │ │  Audit  │ │  Access │ │
│  │ tenant  │ │  Logger │ │ Control │ │
│  │ Manager │ │         │ │         │ │
│  └─────────┘ └─────────┘ └─────────┘ │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │  Agent  │ │  Task   │ │ Output  │ │
│  │ Service │ │ Service │ │ Service │ │
│  └─────────┘ └─────────┘ └─────────┘ │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         Agent Runtime                   │
│    (Configurable external platforms)    │
└─────────────────────────────────────────┘
```

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
# Edit .env file

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

### Agent Management
```
POST   /v1/agents              # Create agent
GET    /v1/agents              # List agents
GET    /v1/agents/{id}         # Get agent details
PUT    /v1/agents/{id}         # Update agent
DELETE /v1/agents/{id}         # Delete agent
```

### Task Management
```
POST   /v1/agents/{id}/tasks   # Assign task
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
├── integrations/           # External platform client and sync
├── services/               # Business logic services
├── cli.py                  # CLI commands
├── config.py               # Configuration
└── main.py                 # Application entry
```

## 🔧 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/hermeswith` |
| `REDIS_URL` | Redis URL | `redis://localhost:6379` |
| `RATE_LIMIT_PER_MINUTE` | Rate limit per minute | `60` |
| `SECRET_KEY` | Encryption key | Auto-generated |
| `DEBUG` | Debug mode | `false` |

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Create Pull Request

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">Made with ❤️ by HermesWith Team</p>
