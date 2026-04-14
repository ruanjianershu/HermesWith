"""Entry point for AgentRuntime in a container."""

import asyncio
import os
import signal
import sys

# Ensure vendor hermes-agent is on path
sys.path.insert(0, "/app/vendor/hermes-agent")

from hermeswith.runtime import AgentConfig, AgentRuntime
from hermeswith.control_plane.goal_queue import RedisGoalQueue


class RuntimeApp:
    """Main application wrapper for AgentRuntime."""
    
    def __init__(self):
        self.runtime: AgentRuntime = None
        self.goal_queue: RedisGoalQueue = None
        self.shutdown_event = asyncio.Event()
        
    def setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        def signal_handler(sig, frame):
            print(f"\n\n📡 Received signal {sig}, initiating graceful shutdown...")
            self.shutdown_event.set()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    async def initialize(self):
        """Initialize the runtime and connections."""
        config = AgentConfig.from_env()
        
        print("=" * 60)
        print(f"🚀 HermesWith Agent Runtime")
        print("=" * 60)
        print(f"Agent ID:    {config.agent_id}")
        print(f"Company:     {config.company_id}")
        print(f"Role:        {config.role}")
        print(f"Model:       {config.model}")
        print(f"Toolsets:    {config.toolsets}")
        print(f"Redis URL:   {config.redis_url}")
        print(f"WebSocket:   {config.control_plane_ws}")
        print("=" * 60)
        
        # Initialize runtime
        self.runtime = AgentRuntime(config)
        
        # Initialize goal queue
        self.goal_queue = RedisGoalQueue(config.redis_url)
        
        # Setup WebSocket connection for notifications
        await self.runtime._notify({
            "type": "agent_registered",
            "agent_id": config.agent_id,
            "status": "online",
        })
        
    async def process_single_goal(self, goal) -> bool:
        """Process a single goal. Returns True if successful."""
        try:
            await self.runtime._execute_goal(goal)
            return True
        except Exception as e:
            print(f"❌ Failed to process goal {goal.id}: {e}")
            # Notify failure
            await self.runtime._notify({
                "type": "goal_failed",
                "goal_id": goal.id,
                "agent_id": self.runtime.agent_id,
                "error": str(e),
            })
            return False
            
    async def run_main_loop(self):
        """Main loop: continuously pull and execute Goals from Redis."""
        config = self.runtime.config
        
        print(f"\n📡 Starting main loop...")
        print(f"   Agent will pull goals from Redis queue: goals:{config.agent_id}")
        print(f"   Press Ctrl+C to stop\n")
        
        while not self.shutdown_event.is_set():
            # Check if agent is paused
            if self.runtime.paused:
                await asyncio.sleep(1)
                continue
                
            try:
                # Pull next goal from queue (with timeout to allow shutdown checks)
                goal = await self.goal_queue.pull(config.agent_id, timeout=1.0)
                
                if goal:
                    print(f"\n📥 Received goal from queue: {goal.id}")
                    await self.process_single_goal(goal)
                else:
                    # No goal available, brief sleep before retry
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️  Error in main loop: {e}")
                await asyncio.sleep(5)
                
    async def shutdown(self):
        """Cleanup resources."""
        print("\n🧹 Cleaning up...")
        
        if self.runtime and self.runtime._ws_client:
            await self.runtime._notify({
                "type": "agent_offline",
                "agent_id": self.runtime.agent_id,
                "status": "offline",
            })
            await self.runtime._ws_client.disconnect()
            
        print("👋 Goodbye!")
        
    async def run(self):
        """Run the complete application lifecycle."""
        self.setup_signal_handlers()
        
        try:
            await self.initialize()
            await self.run_main_loop()
        finally:
            await self.shutdown()


async def main():
    """Entry point."""
    app = RuntimeApp()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
