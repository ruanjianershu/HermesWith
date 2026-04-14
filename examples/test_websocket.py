"""
Test WebSocket client for HermesWith agent updates.

Connects to ws://localhost:8000/ws/agents/{agent_id}
and prints all received messages in real time.

Optionally sends intervention messages.

Usage:
    python examples/test_websocket.py <agent_id>
    # Then type messages to send as interventions,
    # or press Ctrl+C to exit.
"""

import asyncio
import sys

import websockets

API_WS = "ws://localhost:8000/ws/agents/{agent_id}"


async def producer(ws):
    """Read lines from stdin and send as intervention messages."""
    loop = asyncio.get_event_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
        except EOFError:
            break
        if not line:
            break
        text = line.strip()
        if text:
            msg = {"type": "intervene", "message": text}
            await ws.send(msg)
            print(f"  → Sent: {msg}")


async def consumer(ws, agent_id: str):
    """Print all messages received from the WebSocket."""
    async for message in ws:
        print(f"📨 {message}")


async def listen(agent_id: str):
    """Connect to the agent WebSocket and run producer/consumer."""
    url = API_WS.format(agent_id=agent_id)
    print(f"Connecting to {url} ...")

    try:
        async with websockets.connect(url) as ws:
            print(f"✅ Connected. Listening for messages from agent '{agent_id}':")
            print("Type a message and press Enter to send an intervention (Ctrl+C to exit).\n")
            await asyncio.gather(
                consumer(ws, agent_id),
                producer(ws),
                return_exceptions=True,
            )
    except websockets.exceptions.ConnectionRefusedError:
        print("❌ Connection refused. Is the Control Plane running on port 8000?")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "test-agent"
    try:
        asyncio.run(listen(agent_id))
    except KeyboardInterrupt:
        print("\n👋 Disconnected.")
