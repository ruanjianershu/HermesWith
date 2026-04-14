"""
Intervention Queue for user messages during goal execution.
"""

import asyncio
from typing import Any, Dict, Optional


class InterventionQueue:
    """
    Async queue for user interventions sent to a running agent.
    """

    def __init__(self):
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    async def put(self, message: Dict[str, Any]) -> None:
        """Enqueue an intervention message."""
        await self._queue.put(message)

    async def get(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Dequeue the next intervention message.
        Returns None if the timeout expires before a message arrives.
        """
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def empty(self) -> bool:
        """Return True if no interventions are pending."""
        return self._queue.empty()

    def size(self) -> int:
        """Return the number of pending interventions."""
        return self._queue.qsize()
