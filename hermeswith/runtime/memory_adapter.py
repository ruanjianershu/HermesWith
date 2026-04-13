"""Memory adapter for HermesWith AgentRuntime.

Wraps the Hermes memory system with a simple PersistentMemory interface.
Future: add PostgreSQL backend for cross-session persistence.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Memory:
    """A single memory entry."""

    key: str
    value: Any
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.utcnow)


class PersistentMemory:
    """In-memory persistent memory store for AgentRuntime.

    Provides recall/query and save operations. Currently backed by a
    simple dict; PostgreSQL persistence will be added in a future iteration.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Memory] = {}

    def recall(self, query: str, limit: int = 5) -> List[Memory]:
        """Recall memories matching the query.

        Args:
            query: Substring to match against keys and values.
            limit: Maximum number of memories to return.

        Returns:
            List of matching Memory entries, sorted by importance.
        """
        query_lower = query.lower()
        matches = [
            mem
            for mem in self._store.values()
            if query_lower in mem.key.lower()
            or query_lower in str(mem.value).lower()
        ]
        matches.sort(key=lambda m: (-m.importance, m.created_at))
        return matches[:limit]

    def save(self, key: str, value: Any, importance: float = 0.5) -> None:
        """Save a memory entry.

        Args:
            key: Unique identifier for the memory.
            value: The memory content (any JSON-serializable type).
            importance: Relevance score from 0.0 to 1.0.
        """
        self._store[key] = Memory(
            key=key,
            value=value,
            importance=importance,
            created_at=datetime.utcnow(),
        )
