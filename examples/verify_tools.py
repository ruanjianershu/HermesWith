"""
Verify that HermesWith runtime tools are properly registered.

Usage:
    cd /Users/liting/workspace/hermeswith
    export KIMI_API_KEY=***
    python examples/verify_tools.py
"""

import sys
import os

# Ensure vendor hermes-agent is on path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor", "hermes-agent"))

from hermeswith.runtime import AgentConfig, AgentRuntime


def main():
    print("=" * 60)
    print("HermesWith Tool Verification")
    print("=" * 60)
    
    # Check if API key is available
    api_key = os.getenv("KIMI_API_KEY") or os.getenv("AGENT_API_KEY")
    if not api_key:
        print("⚠️  No API key found. Set KIMI_API_KEY or AGENT_API_KEY.")
        print("   Continuing with mock mode...")
    
    # Create config with toolsets including hermeswith-runtime
    config = AgentConfig(
        agent_id="test-agent",
        company_id="test",
        role="assistant",
        model="k2p5",
        api_key=api_key or "dummy",
        toolsets=["terminal", "file", "hermeswith-runtime"],
        max_iterations=10,
    )
    
    print(f"\n📝 Config:")
    print(f"   Agent ID: {config.agent_id}")
    print(f"   Model: {config.model}")
    print(f"   Toolsets: {config.toolsets}")
    
    # Initialize runtime
    print("\n🔧 Initializing AgentRuntime...")
    runtime = AgentRuntime(config)
    
    if not runtime._has_hermes:
        print("⚠️  Hermes AIAgent not available (expected in dev mode without deps)")
        print("   Tools cannot be verified without hermes-agent dependencies.")
        print("   Run this inside the Docker container for full verification.")
        return
    
    # Check tool registry
    print("\n🔍 Checking tool registry...")
    tool_registry = getattr(runtime.agent, "tool_registry", None)
    if tool_registry:
        tool_names = [
            t.get("function", {}).get("name")
            for t in tool_registry
            if isinstance(t, dict) and t.get("function", {}).get("name")
        ]
        print(f"   Registered tools ({len(tool_names)}):")
        for name in sorted(tool_names):
            print(f"      - {name}")
        
        # Check for our runtime tools
        if "goal_complete" in tool_names:
            print("   ✅ goal_complete tool registered")
        else:
            print("   ❌ goal_complete tool NOT found")
            
        if "ask_user" in tool_names:
            print("   ✅ ask_user tool registered")
        else:
            print("   ❌ ask_user tool NOT found")
    else:
        print("   ❌ No tool_registry found on agent")
    
    print("\n" + "=" * 60)
    print("Verification complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
