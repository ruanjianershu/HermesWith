"""
验证脚本：确认 AgentRuntime -> AIAgent -> LLM 这条路能通。

运行方式:
    export KIMI_API_KEY=***
    python examples/verify_llm_path.py
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(sys.path[0], "vendor/hermes-agent"))

from hermeswith.runtime import AgentConfig, AgentRuntime


async def verify():
    print("=" * 60)
    print("🧪 HermesWith LLM 路径验证")
    print("=" * 60)
    
    # 1. 确认有 API Key
    api_key = os.getenv("KIMI_API_KEY", "")
    if not api_key:
        print("❌ 未设置 KIMI_API_KEY 环境变量")
        sys.exit(1)
    print(f"✅ API Key 已设置: {api_key[:10]}...")
    
    # 2. 创建 AgentConfig
    config = AgentConfig(
        agent_id="verify-agent",
        company_id="demo",
        role="tester",
        model="k2p5",
        base_url="https://api.kimi.com/coding/v1",
        api_key=api_key,
        toolsets=[],  # MVP 先不加载工具
        max_iterations=3,
    )
    print(f"✅ AgentConfig 创建成功")
    print(f"   Model: {config.model}")
    print(f"   Base URL: {config.base_url}")
    
    # 3. 初始化 AgentRuntime
    runtime = AgentRuntime(config)
    print(f"✅ AgentRuntime 初始化成功")
    print(f"   Has Hermes: {runtime._has_hermes}")
    
    if not runtime._has_hermes:
        print("❌ Hermes AIAgent 未加载")
        sys.exit(1)
    
    # 4. 直接调用 AIAgent.chat() 验证 LLM 连接
    print("\n📝 Test 1: 直接调用 AIAgent.chat()")
    try:
        result = runtime.agent.chat(
            "Say 'Hello from HermesWith!' and nothing else."
        )
        print(f"✅ LLM 响应: {result}")
        assert "Hello from HermesWith" in result, f"Unexpected response: {result}"
    except Exception as e:
        print(f"❌ LLM 调用失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # 5. 通过 AgentRuntime 执行 Goal
    print("\n📝 Test 2: 通过 AgentRuntime 执行 Goal")
    try:
        goal = await runtime.submit_goal(
            "Say 'HermesWith is working!' and nothing else.",
            context={"test": True}
        )
        execution = runtime.current_execution
        print(f"✅ Goal 执行完成: {goal.id}")
        print(f"   Status: {execution.status}")
        print(f"   Output: {execution.final_output}")
        assert "HermesWith is working" in execution.final_output
    except Exception as e:
        print(f"❌ Goal 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("🎉 所有验证通过！AgentRuntime -> AIAgent -> LLM 链路已打通")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(verify())
