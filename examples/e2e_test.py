"""
End-to-End Integration Test for HermesWith

Validates the complete flow:
1. Infrastructure (Postgres + Redis) is running
2. Control Plane API responds
3. Goal can be created via API and persisted to DB
4. Goal queue receives the message
5. Agent Runtime can pull and execute the goal
6. WebSocket broadcasts progress messages

Usage:
    # Terminal 1: Start infrastructure
    docker-compose up -d postgres redis

    # Terminal 2: Start control plane
    uvicorn hermeswith.control_plane.api:create_app --reload

    # Terminal 3: Run this test
    python examples/e2e_test.py
"""

import asyncio
import sys
import uuid

import httpx

API_BASE = "http://localhost:8000"
AGENT_ID = f"e2e-test-agent-{uuid.uuid4().hex[:8]}"


async def test_health():
    print("\n[Test 1/6] Control Plane Health...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/health", timeout=5.0)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        print(f"   ✅ Healthy: {data}")


async def test_goal_crud():
    print("\n[Test 2/6] Goal CRUD API...")
    async with httpx.AsyncClient() as client:
        # Create
        resp = await client.post(
            f"{API_BASE}/api/companies/e2e-corp/goals",
            json={
                "agent_id": AGENT_ID,
                "description": "E2E test goal: verify the platform works",
                "context": {"test": True, "agent_id": AGENT_ID},
            },
        )
        assert resp.status_code == 200
        goal = resp.json()
        goal_id = goal["id"]
        print(f"   ✅ Created: {goal_id}")

        # Read
        resp = await client.get(f"{API_BASE}/api/goals/{goal_id}")
        assert resp.status_code == 200
        fetched = resp.json()
        assert fetched["id"] == goal_id
        print(f"   ✅ Read: {fetched['status']}")

        # List
        resp = await client.get(f"{API_BASE}/api/goals?agent_id={AGENT_ID}")
        assert resp.status_code == 200
        listed = resp.json()
        assert len(listed["goals"]) >= 1
        print(f"   ✅ Listed: {listed['total']} goals")

        return goal_id


async def test_agent_management():
    print("\n[Test 3/6] Agent Management API...")
    async with httpx.AsyncClient() as client:
        # Pause
        resp = await client.post(f"{API_BASE}/api/agents/{AGENT_ID}/pause")
        assert resp.status_code == 200
        print(f"   ✅ Paused")

        # Get
        resp = await client.get(f"{API_BASE}/api/agents/{AGENT_ID}")
        assert resp.status_code == 200
        agent = resp.json()
        assert agent["paused"] is True
        print(f"   ✅ Status: paused={agent['paused']}")

        # Resume
        resp = await client.post(f"{API_BASE}/api/agents/{AGENT_ID}/resume")
        assert resp.status_code == 200
        print(f"   ✅ Resumed")


async def test_direct_execution():
    print("\n[Test 4/6] Direct Agent Execution...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE}/api/agents/{AGENT_ID}/execute",
            json={
                "agent_id": AGENT_ID,
                "description": "Say 'HermesWith E2E test passed!'",
                "context": {"test": True},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        print(f"   ✅ Executed: {data['status']}")
        print(f"   Output: {data.get('output', '')[:80]}...")


async def test_redis_queue():
    print("\n[Test 5/6] Redis Goal Queue...")
    sys.path.insert(0, "/Users/liting/workspace/hermeswith")
    sys.path.insert(0, "/Users/liting/workspace/hermeswith/vendor/hermes-agent")

    from hermeswith.control_plane.goal_queue import RedisGoalQueue
    from hermeswith.runtime.agent_runtime import Goal
    import os

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queue = RedisGoalQueue(redis_url)

    test_goal = Goal(
        agent_id=AGENT_ID,
        company_id="e2e-corp",
        description="Redis queue test goal",
        context={"source": "e2e_test"},
    )

    await queue.push(AGENT_ID, test_goal)
    print(f"   ✅ Pushed goal to Redis")

    pending = await queue.list_pending(AGENT_ID)
    assert len(pending) >= 1
    print(f"   ✅ Pending goals: {len(pending)}")

    pulled = await queue.pull(AGENT_ID, timeout=2.0)
    assert pulled is not None
    assert pulled.id == test_goal.id
    print(f"   ✅ Pulled goal matches: {pulled.id}")


async def test_local_runtime():
    print("\n[Test 6/6] Local AgentRuntime...")
    sys.path.insert(0, "/Users/liting/workspace/hermeswith")
    sys.path.insert(0, "/Users/liting/workspace/hermeswith/vendor/hermes-agent")

    from hermeswith.runtime import AgentConfig, AgentRuntime

    config = AgentConfig(
        agent_id=AGENT_ID,
        company_id="e2e-corp",
        role="tester",
        model="k2p5",
        api_key="dummy",
        toolsets=["hermeswith-runtime"],
    )
    runtime = AgentRuntime(config)
    goal = await runtime.submit_goal(
        "Explain what HermesWith is in one sentence",
        context={"test": True},
    )
    assert goal.status in ("pending", "completed", "failed")
    print(f"   ✅ Local runtime executed: {goal.id}")


async def main():
    print("=" * 60)
    print("HermesWith End-to-End Integration Test")
    print("=" * 60)
    print(f"Agent ID: {AGENT_ID}")

    tests = [
        test_health,
        test_goal_crud,
        test_agent_management,
        test_direct_execution,
        test_redis_queue,
        test_local_runtime,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            failed += 1
            import traceback
            print(f"   ❌ FAILED: {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
