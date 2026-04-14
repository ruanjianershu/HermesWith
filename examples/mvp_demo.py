"""
MVP Demo for HermesWith

Tests:
1. Control Plane API is running
2. AgentRuntime can be instantiated
3. Goal can be submitted and executed
"""

import asyncio
import httpx

API_BASE = "http://localhost:8000"


async def test_health():
    """Test 1: Control Plane is alive."""
    print("\n[Test 1] Health check...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{API_BASE}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        print(f"✅ Control Plane is healthy: {data}")


async def test_create_goal():
    """Test 2: Create a Goal via API."""
    print("\n[Test 2] Create goal...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE}/api/companies/demo/goals",
            json={
                "agent_id": "researcher-001",
                "description": "Search for the latest Python release and summarize it",
                "context": {"format": "markdown"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        print(f"✅ Goal created: {data['id']} (status: {data['status']})")
        return data["id"]


async def test_direct_execution():
    """Test 3: Execute a Goal directly on an Agent."""
    print("\n[Test 3] Direct agent execution...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE}/api/agents/researcher-001/execute",
            json={
                "agent_id": "researcher-001",
                "description": "Say hello from HermesWith and explain what you are",
                "context": {"test": True},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        print(f"✅ Direct execution result:")
        print(f"   Goal ID: {data['goal_id']}")
        print(f"   Status:  {data['status']}")
        print(f"   Output:  {data['output'][:100]}...")


async def test_local_runtime():
    """Test 4: Run AgentRuntime locally without API."""
    print("\n[Test 4] Local AgentRuntime execution...")
    import sys
    sys.path.insert(0, "/Users/liting/workspace/hermeswith")
    
    from hermeswith.runtime import AgentConfig, AgentRuntime
    
    config = AgentConfig(
        agent_id="test-agent",
        company_id="demo",
        role="tester",
        model="kimi-k2.5",
        toolsets=[],
    )
    runtime = AgentRuntime(config)
    goal = await runtime.submit_goal(
        "Explain what HermesWith is in one sentence",
        context={"test": True},
    )
    print(f"✅ Local execution: {goal.id}")


async def main():
    print("=" * 60)
    print("HermesWith MVP Demo")
    print("=" * 60)
    
    try:
        await test_health()
    except Exception as e:
        print(f"⚠️  Control Plane not running. Start it with:")
        print(f"   cd /Users/liting/workspace/hermeswith")
        print(f"   uvicorn hermeswith.control_plane.api:create_app --reload")
        print(f"   Error: {e}")
    
    try:
        await test_create_goal()
    except Exception as e:
        print(f"❌ Goal creation failed: {e}")
    
    try:
        await test_direct_execution()
    except Exception as e:
        print(f"❌ Direct execution failed: {e}")
    
    try:
        await test_local_runtime()
    except Exception as e:
        print(f"❌ Local runtime failed: {e}")
    
    print("\n" + "=" * 60)
    print("MVP Demo completed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
