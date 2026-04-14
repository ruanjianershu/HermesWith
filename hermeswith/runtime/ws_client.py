"""
WebSocket Client for AgentRuntime.

Handles persistent WebSocket connections with automatic reconnection.
"""

import asyncio
import json
from typing import Any, Dict, Optional

import websockets


class WSClient:
    """
    Persistent WebSocket client with exponential-backoff reconnect.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.url: Optional[str] = None
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._stop_reconnect = False
        self._lock = asyncio.Lock()

        # Reconnect config
        self._reconnect_interval = 1.0
        self._max_reconnect_interval = 30.0
        self._reconnect_backoff = 2.0

    async def connect(self, url: str) -> None:
        """Connect to the WebSocket endpoint and start the reconnect loop."""
        self.url = url
        self._stop_reconnect = False
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Maintain connection with exponential backoff."""
        while not self._stop_reconnect:
            try:
                if not self._connected and self.url:
                    async with self._lock:
                        self._ws = await websockets.connect(self.url)
                        self._connected = True
                        self._reconnect_interval = 1.0
                        print(f"🔌 WSClient connected: {self.url}")
                # While connected, just wait and monitor
                while self._connected and not self._stop_reconnect:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"⚠️  WSClient connection error: {e}")
                async with self._lock:
                    self._connected = False
                    self._ws = None
                await asyncio.sleep(self._reconnect_interval)
                self._reconnect_interval = min(
                    self._reconnect_interval * self._reconnect_backoff,
                    self._max_reconnect_interval,
                )

    async def send(self, message: Dict[str, Any]) -> bool:
        """Send a JSON message. Returns True on success."""
        async with self._lock:
            if self._connected and self._ws:
                try:
                    await self._ws.send(json.dumps(message))
                    return True
                except Exception as e:
                    print(f"⚠️  WSClient send failed: {e}")
                    self._connected = False
                    self._ws = None
            return False

    async def disconnect(self) -> None:
        """Gracefully disconnect and stop reconnecting."""
        self._stop_reconnect = True
        async with self._lock:
            if self._ws:
                try:
                    await self._ws.close()
                except Exception:
                    pass
            self._ws = None
            self._connected = False
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
