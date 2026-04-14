"""
Goal Queue - Redis-backed queue for agent goals.
"""

import asyncio
import json
from typing import Dict, List, Optional

from hermeswith.runtime.agent_runtime import Goal


class RedisGoalQueue:
    """
    Redis-backed queue for Goals.
    Falls back to in-memory dict if Redis is unavailable (MVP mode).
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._redis_url = redis_url
        self._redis = None
        self._fallback: Dict[str, List[Goal]] = {}
        self._lock = asyncio.Lock()

        try:
            import redis.asyncio as redis_lib

            self._redis = redis_lib.from_url(redis_url, decode_responses=True)
            # Don't await here in __init__, check lazily
        except Exception as e:
            print(f"⚠️  Redis unavailable, using in-memory fallback: {e}")
            self._redis = None

    def _key(self, agent_id: str) -> str:
        return f"goals:{agent_id}"

    async def _ensure_connection(self) -> bool:
        """Ensure Redis connection is alive. Returns True if connected."""
        if self._redis is None:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            self._redis = None
            return False

    async def push(self, agent_id: str, goal: Goal) -> None:
        """Push a Goal to the agent's queue."""
        data = goal.model_dump_json()
        if await self._ensure_connection():
            await self._redis.lpush(self._key(agent_id), data)
        else:
            async with self._lock:
                self._fallback.setdefault(agent_id, []).append(goal)

    async def pull(self, agent_id: str, timeout: float = 1.0) -> Optional[Goal]:
        """Pull the next Goal from the agent's queue."""
        if await self._ensure_connection():
            data = await self._redis.brpop(self._key(agent_id), timeout=timeout)
            if data:
                _, raw = data
                return Goal.model_validate_json(raw)
            return None
        else:
            async with self._lock:
                queue = self._fallback.get(agent_id, [])
                if queue:
                    return queue.pop(0)
                return None

    async def list_pending(self, agent_id: str) -> List[Goal]:
        """List all pending Goals for an agent."""
        if await self._ensure_connection():
            raw_items = await self._redis.lrange(self._key(agent_id), 0, -1)
            return [Goal.model_validate_json(raw) for raw in raw_items]
        else:
            async with self._lock:
                return list(self._fallback.get(agent_id, []))

    async def remove(self, agent_id: str, goal_id: str) -> bool:
        """Remove a specific goal by ID from the queue. Returns True if removed."""
        if await self._ensure_connection():
            # Find and remove by goal ID (inefficient but works for MVP)
            raw_items = await self._redis.lrange(self._key(agent_id), 0, -1)
            for raw in raw_items:
                try:
                    goal = Goal.model_validate_json(raw)
                    if goal.id == goal_id:
                        await self._redis.lrem(self._key(agent_id), 0, raw)
                        return True
                except Exception:
                    continue
            return False
        else:
            async with self._lock:
                queue = self._fallback.get(agent_id, [])
                for i, goal in enumerate(queue):
                    if goal.id == goal_id:
                        queue.pop(i)
                        return True
                return False
