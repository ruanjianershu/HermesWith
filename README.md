# HermesWith

Multi-tenant agent management API with Clawith integration.

## Features

- **Multi-tenant**: Company-based isolation with API key authentication
- **Agent Management**: Create, update, delete agents with Clawith sync
- **Task Management**: Assign tasks to agents with priority and status tracking
- **Audit Logging**: Complete audit trail of all API requests
- **Rate Limiting**: Redis-backed rate limiting per API key
- **Encryption**: Fernet encryption for sensitive configuration

## Quick Start

### Using Docker Compose

```bash
# Start services
docker-compose up -d

# Create a company and get API key
docker-compose exec api python -m hermeswith.cli create-company "My Company"

# Create an API key
docker-compose exec api python -m hermeswith.cli create-api-key <company-id>
```

### Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python -m hermeswith.cli init-db

# Create company and API key
python -m hermeswith.cli create-company "My Company"
python -m hermeswith.cli create-api-key <company-id>

# Run API server
uvicorn hermeswith.main:app --reload
```

## API Endpoints

- `GET /health` - Health check
- `POST /v1/agents` - Create agent
- `GET /v1/agents` - List agents
- `GET /v1/agents/{id}` - Get agent
- `PUT /v1/agents/{id}` - Update agent
- `DELETE /v1/agents/{id}` - Delete agent
- `POST /v1/agents/{id}/tasks` - Create task for agent
- `GET /v1/tasks/{id}` - Get task
- `GET /v1/tasks/{id}/output` - Get task output

## Authentication

Use API key in header:
```
X-API-Key: hw_<your-api-key>
```

Or use Bearer token:
```
Authorization: Bearer <jwt-token>
```

## Project Structure

```
hermeswith/
├── api/              # FastAPI routes and middleware
├── persistence/      # Database models and connection
├── security/         # Auth, encryption, rate limiting, audit
├── integrations/     # Clawith client and sync
├── services/         # Business logic
├── cli.py           # CLI commands
├── config.py        # Configuration
└── main.py          # FastAPI app entry
```

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection string
- `CLAWITH_BASE_URL` - Clawith API URL
- `CLAWITH_API_KEY` - Clawith API key
- `REDIS_URL` - Redis connection string
- `RATE_LIMIT_PER_MINUTE` - Default rate limit

## License

MIT
