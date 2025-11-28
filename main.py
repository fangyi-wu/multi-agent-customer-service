"""
Multi-Agent Customer Service System - Main Demo
================================================
This script runs the complete multi-agent system demonstration.

Architecture:
- MCP Server (port 8000): Exposes customer database tools via SSE
- Customer Data Agent (port 8001): A2A agent for data operations
- Support Agent (port 8002): A2A agent for support operations  
- Router Agent (port 8003): A2A orchestrator agent

To run:
    python main.py

Requirements:
    - Google API Key (GOOGLE_API_KEY environment variable)
    - All dependencies installed (see requirements.txt)
"""

import os
import sys
import json
import asyncio
import subprocess
import time
import httpx
from typing import Optional

# Check for API key
if not os.getenv("GOOGLE_API_KEY"):
    print("="*60)
    print("ERROR: GOOGLE_API_KEY environment variable not set!")
    print("="*60)
    print("\nPlease set your Google API key:")
    print("  export GOOGLE_API_KEY=your_api_key_here")
    print("\nGet a key from: https://aistudio.google.com/app/apikey")
    print("="*60)
    sys.exit(1)


class A2ATestClient:
    """Simple A2A client for testing agents."""
    
    def __init__(self, agent_url: str):
        self.agent_url = agent_url.rstrip('/')
    
    async def get_agent_card(self) -> dict:
        """Fetch the agent card."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.agent_url}/.well-known/agent.json")
                if response.status_code == 200:
                    return response.json()
                return {"error": f"Status {response.status_code}"}
            except Exception as e:
                return {"error": str(e)}
    
    async def send_message(self, message: str) -> dict:
        """Send a message to the agent."""
        import uuid
        task_id = str(uuid.uuid4())
        
        request = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": task_id,
                "message": {
                    "role": "user",
                    "parts": [{"text": message}]
                }
            },
            "id": task_id
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.agent_url,
                    json=request,
                    headers={"Content-Type": "application/json"}
                )
                return response.json()
            except Exception as e:
                return {"error": str(e)}


async def test_mcp_server():
    """Test the MCP server is running and responsive."""
    print("\n" + "="*60)
    print("Testing MCP Server (http://localhost:8000/sse)")
    print("="*60)
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # MCP servers typically respond to OPTIONS or have a health endpoint
            response = await client.get("http://localhost:8000/sse")
            print(f"✅ MCP Server is responding (status: {response.status_code})")
            return True
    except Exception as e:
        print(f"❌ MCP Server not responding: {e}")
        return False


async def test_agent(name: str, url: str):
    """Test an A2A agent."""
    print(f"\nTesting {name} ({url})")
    print("-" * 40)
    
    client = A2ATestClient(url)
    
    # Test agent card
    card = await client.get_agent_card()
    if "error" not in card:
        print(f"✅ Agent Card retrieved: {card.get('name', 'unknown')}")
        print(f"   Skills: {[s.get('name') for s in card.get('skills', [])]}")
    else:
        print(f"❌ Agent Card error: {card.get('error')}")
        return False
    
    return True


async def run_test_scenario(scenario_num: int, name: str, query: str, description: str):
    """Run a single test scenario."""
    print(f"\n{'#'*60}")
    print(f"# TEST SCENARIO {scenario_num}: {name}")
    print(f"{'#'*60}")
    print(f"Query: \"{query}\"")
    print(f"Expected: {description}")
    print("-" * 60)
    
    # Send to router agent
    client = A2ATestClient("http://localhost:8003")
    result = await client.send_message(query)
    
    print("\nResponse:")
    print(json.dumps(result, indent=2, default=str)[:1000])
    
    return result


async def run_demo():
    """Run the complete demo."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     MULTI-AGENT CUSTOMER SERVICE SYSTEM                              ║
║     with A2A Protocol and MCP Integration                            ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    print("\nThis demo requires the following services to be running:")
    print("  1. MCP Server (port 8000) - Run: python mcp_server.py")
    print("  2. Customer Data Agent (port 8001) - Run: python customer_data_agent.py")
    print("  3. Support Agent (port 8002) - Run: python support_agent.py")
    print("  4. Router Agent (port 8003) - Run: python router_agent.py")
    print("\nPress Enter when all services are running...")
    input()
    
    # Test all components
    print("\n" + "="*60)
    print("STEP 1: Testing Components")
    print("="*60)
    
    mcp_ok = await test_mcp_server()
    
    agents_ok = True
    for name, url in [
        ("Customer Data Agent", "http://localhost:8001"),
        ("Support Agent", "http://localhost:8002"),
        ("Router Agent", "http://localhost:8003")
    ]:
        if not await test_agent(name, url):
            agents_ok = False
    
    if not (mcp_ok and agents_ok):
        print("\n⚠️ Some components are not running. Please start all services.")
        return
    
    print("\n✅ All components are running!")
    
    # Run test scenarios
    print("\n" + "="*60)
    print("STEP 2: Running Test Scenarios")
    print("="*60)
    
    scenarios = [
        (1, "Simple Query (Task Allocation)", 
         "Get customer information for ID 5",
         "Single agent, straightforward MCP call via Customer Data Agent"),
        
        (2, "Coordinated Query",
         "I'm customer 1 and need help upgrading my account",
         "Multiple agents: Customer Data Agent + Support Agent"),
        
        (3, "Complex Query (Report)",
         "Show me all active customers who have open tickets",
         "Customer Data Agent generates report"),
        
        (4, "Escalation (Urgent Issue)",
         "I've been charged twice, please refund immediately!",
         "Support Agent handles urgent billing with escalation"),
        
        (5, "Multi-Intent Query",
         "Update my email to new@email.com and show my ticket history for customer ID 2",
         "Parallel: Customer Data Agent updates + retrieves history")
    ]
    
    for num, name, query, desc in scenarios:
        await run_test_scenario(num, name, query, desc)
        print("\nPress Enter for next scenario...")
        input()
    
    # Summary
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("""
Key Features Demonstrated:
✅ MCP Protocol: Database tools exposed via SSE transport
✅ A2A Protocol: Agents communicate via standard A2A interface
✅ Agent Cards: Each agent publishes capabilities via .well-known/agent.json
✅ Task Routing: Router analyzes intent and delegates to specialists
✅ Multi-Agent Coordination: Complex queries handled by multiple agents

To test with MCP Inspector:
  npx @modelcontextprotocol/inspector
  Connect to: http://localhost:8000/sse

To test with A2A Inspector:
  Visit: https://a2a-inspector.vercel.app/
  Connect to: http://localhost:8001, 8002, or 8003
""")


if __name__ == "__main__":
    asyncio.run(run_demo())
