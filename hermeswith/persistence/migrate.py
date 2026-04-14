"""Database migration script using asyncpg directly.

Run with: python -m hermeswith.persistence.migrate
"""

import asyncio
import os

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://hermeswith:hermeswith@localhost:5432/hermeswith",
)

# Strip +asyncpg if present for asyncpg direct connection
CLEAN_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

CREATE_TABLES_SQL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

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
"""


async def migrate() -> None:
    conn = await asyncpg.connect(CLEAN_URL)
    try:
        await conn.execute(CREATE_TABLES_SQL)
        print("Migration completed successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
