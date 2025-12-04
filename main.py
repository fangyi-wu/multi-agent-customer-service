"""
Multi-Agent Customer Service System - Demo Runner
==================================================
Runs all test scenarios against the multi-agent system.

Prerequisites (start in separate terminals):
    Terminal 1: python mcp_server.py           (Port 8000)
    Terminal 2: python customer_data_agent.py  (Port 8001)
    Terminal 3: python support_agent.py        (Port 8002)
    Terminal 4: python router_agent.py         (Port 8003)

Then run:
    python main.py
"""

import json
import asyncio
import httpx


class A2ATestClient:
    """Simple A2A client for testing."""
    
    def __init__(self, agent_url: str):
        self.agent_url = agent_url.rstrip('/')
    
    async def get_agent_card(self) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.agent_url}/.well-known/agent.json")
                if response.status_code == 200:
                    return response.json()
                return {"error": f"Status {response.status_code}"}
            except Exception as e:
                return {"error": str(e)}
    
    async def send_message(self, message: str) -> dict:
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
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    self.agent_url,
                    json=request,
                    headers={"Content-Type": "application/json"}
                )
                return response.json()
            except Exception as e:
                return {"error": str(e)}


async def check_mcp_server():
    """Check if MCP server is running."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/sse")
            return True
    except:
        return False


async def check_agent(url: str, name: str):
    """Check if an A2A agent is running."""
    client = A2ATestClient(url)
    card = await client.get_agent_card()
    
    if "error" not in card:
        print(f"  ✅ {name}: Online")
        print(f"     Name: {card.get('name', 'unknown')}")
        print(f"     Skills: {len(card.get('skills', []))}")
        return True
    else:
        print(f"  ❌ {name}: Offline - {card.get('error')}")
        return False


async def run_test(client: A2ATestClient, query: str):
    """Run a test and extract response."""
    response = await client.send_message(query)
    
    if "error" in response:
        return f"Error: {response['error']}"
    
    if "result" in response:
        result = response["result"]
        if "artifacts" in result and result["artifacts"]:
            texts = []
            for artifact in result["artifacts"]:
                if "parts" in artifact:
                    for part in artifact["parts"]:
                        if "text" in part:
                            texts.append(part["text"])
            return "\n".join(texts)
        return json.dumps(result, indent=2, default=str)
    
    return json.dumps(response, indent=2, default=str)


async def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     MULTI-AGENT CUSTOMER SERVICE SYSTEM                              ║
║     with A2A Protocol and MCP Integration                            ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Health checks
    print("="*70)
    print("STEP 1: HEALTH CHECKS")
    print("="*70)
    
    print("\n📡 MCP Server (Port 8000):")
    if await check_mcp_server():
        print("  ✅ MCP Server: Online (SSE endpoint ready)")
    else:
        print("  ❌ MCP Server: Offline")
        print("     Run: python mcp_server.py")
    
    print("\n🤖 A2A Agents:")
    agents_ok = True
    for url, name in [
        ("http://localhost:8001", "Customer Data Agent (Port 8001)"),
        ("http://localhost:8002", "Support Agent (Port 8002)"),
        ("http://localhost:8003", "Router Agent (Port 8003)")
    ]:
        if not await check_agent(url, name):
            agents_ok = False
    
    if not agents_ok:
        print("\n⚠️  Some components are not running!")
        print("\nPlease start all servers first:")
        print("  Terminal 1: python mcp_server.py")
        print("  Terminal 2: python customer_data_agent.py")
        print("  Terminal 3: python support_agent.py")
        print("  Terminal 4: python router_agent.py")
        return
    
    print("\n✅ All components are healthy!")
    input("\nPress Enter to run test scenarios...")
    
    # Test scenarios
    print("\n" + "="*70)
    print("STEP 2: RUNNING TEST SCENARIOS")
    print("="*70)
    
    router_client = A2ATestClient("http://localhost:8003")
    
    scenarios = [
        ("Scenario 1: Simple Query (Task Allocation)",
         "Get customer information for ID 5",
         "Single agent → Customer Data Agent → MCP get_customer"),
        
        ("Scenario 2: Coordinated Query",
         "I'm customer 1 and need help upgrading my account",
         "Multi-agent → Data Agent + Support Agent"),
        
        ("Scenario 3: Complex Query (Report)",
         "Show me all active customers who have open tickets",
         "Customer Data Agent → MCP get_active_customers_with_open_tickets"),
        
        ("Scenario 4: Escalation (Urgent)",
         "I've been charged twice, please refund immediately!",
         "Support Agent → Urgent + Billing escalation"),
        
        ("Scenario 5: Multi-Intent",
         "Update my email to new@email.com and show ticket history for customer ID 2",
         "Customer Data Agent → Update + History")
    ]
    
    for i, (name, query, expected) in enumerate(scenarios, 1):
        print(f"\n{'#'*70}")
        print(f"# TEST {i}: {name}")
        print(f"{'#'*70}")
        print(f"Query: \"{query}\"")
        print(f"Expected Flow: {expected}")
        print("-" * 70)
        
        response = await run_test(router_client, query)
        print(f"\n📋 Response:\n{response}")
        
        if i < len(scenarios):
            input("\n[Press Enter for next scenario]")
    
    # Summary
    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("""
✅ Features Demonstrated:

1. MCP PROTOCOL:
   • Server with SSE transport at http://localhost:8000/sse
   • tools/list returns all available database tools
   • tools/call executes tools (get_customer, create_ticket, etc.)
   • Testable via: npx @modelcontextprotocol/inspector

2. A2A PROTOCOL:
   • Three independent agents with proper Agent Cards
   • Agent Cards at /.well-known/agent.json
   • Tasks/send for receiving A2A messages
   • Router coordinates via A2A protocol

3. TEST SCENARIOS:
   ✓ Task Allocation (single agent routing)
   ✓ Coordinated Query (multi-agent)
   ✓ Complex Query (MCP report generation)
   ✓ Escalation (urgent handling)
   ✓ Multi-Intent (parallel operations)

To verify:
  • MCP Inspector: npx @modelcontextprotocol/inspector → http://localhost:8000/sse
  • Agent Cards: curl http://localhost:8001/.well-known/agent.json
    """)


if __name__ == "__main__":
    asyncio.run(main())
