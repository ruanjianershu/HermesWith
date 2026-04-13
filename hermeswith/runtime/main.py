"""Entry point for AgentRuntime in a container."""

import asyncio
import sys

from hermeswith.runtime import AgentConfig, AgentRuntime


async def main():
    """Start the AgentRuntime."""
    config = AgentConfig.from_env()
    runtime = AgentRuntime(config)
    
    print("=" * 60)
    print(f"🚀 HermesWith Agent Runtime")
    print("=" * 60)
    print(f"Agent ID: {config.agent_id}")
    print(f"Company:  {config.company_id}")
    print(f"Role:     {config.role}")
    print(f"Model:    {config.model}")
    print("=" * 60)
    
    try:
        await runtime.run()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
