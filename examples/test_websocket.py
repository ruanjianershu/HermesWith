"""
Test WebSocket client for HermesWith agent updates.

Connects to ws://localhost:8000/ws/agents/{agent_id}
and prints all received messages in real time.
"""

import asyncio
import sys

import websockets

API_WS = "ws://localhost:8000/ws/agents/{agent_id}"


async def listen(agent_id: str):
    """Connect to the agent WebSocket and print messages."""
    url = API_WS.format(agent_id=agent_id)
    print(f"Connecting to {url} ...")

    try:
        async with websockets.connect(url) as ws:
            print(f"✅ Connected. Listening for messages from agent '{agent_id}':\n")
            async for message in ws:
                print(f"📨 {message}")
    except websockets.exceptions.ConnectionRefusedError:
        print("❌ Connection refused. Is the Control Plane running on port 8000?")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "test-agent"
    asyncio.run(listen(agent_id))
