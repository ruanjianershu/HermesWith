#!/bin/bash
# Start all HermesWith services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🚀 Starting HermesWith services..."

# Prepare vendor for Docker build
echo "📦 Preparing vendor dependencies..."
./scripts/prepare-build.sh

# Start infrastructure
echo "🗄️  Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for PostgreSQL
sleep 3

# Run migrations
echo "🔄 Running database migrations..."
docker run --rm --network hermeswith_default \
  hermeswith-runtime python -c "
import asyncio
import asyncpg
async def migrate():
    conn = await asyncpg.connect(
        host='hermeswith-postgres',
        port=5432,
        user='hermeswith',
        password='hermeswith',
        database='hermeswith'
    )
    sql = '''
CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";
CREATE TABLE IF NOT EXISTS goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR NOT NULL,
    company_id VARCHAR NOT NULL,
    description TEXT NOT NULL,
    context JSONB DEFAULT '{}',
    status VARCHAR DEFAULT 'pending' NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_goals_agent_id ON goals(agent_id);
CREATE INDEX IF NOT EXISTS idx_goals_company_id ON goals(company_id);
CREATE TABLE IF NOT EXISTS goal_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    agent_id VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'pending' NOT NULL,
    final_output TEXT DEFAULT '',
    trajectory JSONB DEFAULT '[]',
    tool_calls JSONB DEFAULT '[]',
    token_usage INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS agent_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR NOT NULL,
    memory_type VARCHAR NOT NULL,
    key VARCHAR NOT NULL,
    value TEXT NOT NULL,
    importance FLOAT DEFAULT 0.5 NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_memories_agent_id ON agent_memories(agent_id);
'''
    await conn.execute(sql)
    print('✅ Database migration completed')
    await conn.close()
asyncio.run(migrate())
"

# Start Control Plane
echo "🎛️  Starting Control Plane..."
docker-compose up -d control-plane

# Wait for Control Plane
sleep 2

# Check health
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Control Plane is healthy"
else
    echo "⚠️  Control Plane may not be ready yet"
fi

echo ""
echo "========================================"
echo "✅ HermesWith is starting up!"
echo "========================================"
echo "Services:"
echo "  📊 Control Plane API: http://localhost:8000"
echo "  📖 API Documentation: http://localhost:8000/docs"
echo "  🗄️  PostgreSQL: localhost:5432"
echo "  💾 Redis: localhost:6379"
echo ""
echo "To start an Agent Runtime:"
echo "  docker-compose up -d researcher"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop all services:"
echo "  docker-compose down"
echo "========================================"
