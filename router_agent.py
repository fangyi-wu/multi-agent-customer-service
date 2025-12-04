"""
Router Agent (Orchestrator) - A2A Server
=========================================
The main orchestrator that routes queries to specialist agents via A2A.
Uses the a2a-python SDK directly - NO external LLM API required.

To run:
    python router_agent.py

Agent will be available at:
    - A2A endpoint: http://localhost:8003
    - Agent Card: http://localhost:8003/.well-known/agent.json

Prerequisites:
    - Customer Data Agent at http://localhost:8001
    - Support Agent at http://localhost:8002
"""

import re
import json
import asyncio
import httpx
from typing import List, Dict, Any

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.types import (
    AgentCard, AgentSkill, AgentCapabilities,
    Task, TaskState, TaskStatus, Message, TextPart, Artifact
)
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
import uvicorn


# =============================================================================
# Agent Card Definition
# =============================================================================

AGENT_CARD = AgentCard(
    name="router_agent",
    description="Router Agent (Orchestrator) - Analyzes queries and routes to "
                "specialist agents (Customer Data Agent, Support Agent) via A2A protocol.",
    url="http://localhost:8003",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=False, pushNotifications=False),
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
    skills=[
        AgentSkill(
            id="analyze_intent",
            name="Analyze Intent",
            description="Analyze customer query to determine intent and routing"
        ),
        AgentSkill(
            id="route_to_data_agent",
            name="Route to Data Agent",
            description="Route data queries to Customer Data Agent via A2A"
        ),
        AgentSkill(
            id="route_to_support_agent",
            name="Route to Support Agent",
            description="Route support queries to Support Agent via A2A"
        ),
        AgentSkill(
            id="coordinate",
            name="Coordinate",
            description="Coordinate multi-agent requests for complex queries"
        )
    ]
)


# =============================================================================
# A2A Client for Remote Agents
# =============================================================================

class A2AClient:
    """Client for communicating with remote A2A agents."""
    
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
    
    async def send_task(self, message: str) -> dict:
        """Send a task to the remote agent via A2A protocol."""
        import uuid
        task_id = str(uuid.uuid4())
        
        # A2A JSON-RPC request format
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


# Remote agent clients
data_agent_client = A2AClient("http://localhost:8001")
support_agent_client = A2AClient("http://localhost:8002")


# =============================================================================
# Intent Analysis
# =============================================================================

def analyze_intent(query: str) -> dict:
    """Analyze query to determine intent(s) and extract parameters."""
    query_lower = query.lower()
    intents = []
    params = {}
    
    # Data-related intents
    if any(w in query_lower for w in ["get customer", "customer id", "customer info", "who is"]):
        intents.append("get_customer")
    if any(w in query_lower for w in ["ticket history", "my tickets", "show tickets"]):
        intents.append("view_history")
    if any(w in query_lower for w in ["update", "change email", "change phone"]):
        intents.append("update_customer")
    if any(w in query_lower for w in ["all active", "report", "open tickets"]):
        intents.append("report")
    if any(w in query_lower for w in ["list customers", "show customers"]):
        intents.append("list_customers")
    
    # Support-related intents
    if any(w in query_lower for w in ["billing", "charge", "invoice", "payment", "refund"]):
        intents.append("billing")
    if any(w in query_lower for w in ["cancel", "cancellation"]):
        intents.append("cancellation")
    if any(w in query_lower for w in ["upgrade", "premium"]):
        intents.append("upgrade")
    if any(w in query_lower for w in ["urgent", "immediately", "asap", "emergency"]):
        intents.append("urgent")
    
    # Extract parameters
    id_match = re.search(r'(?:customer\s*(?:id)?|id)\s*(\d+)', query_lower)
    if id_match:
        params["customer_id"] = int(id_match.group(1))
    
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', query)
    if email_match:
        params["email"] = email_match.group()
    
    if not intents:
        intents.append("general")
    
    # Determine routing
    data_intents = ["get_customer", "view_history", "update_customer", "report", "list_customers"]
    support_intents = ["billing", "cancellation", "upgrade", "urgent", "general"]
    
    routing = {
        "data_agent": [i for i in intents if i in data_intents],
        "support_agent": [i for i in intents if i in support_intents]
    }
    
    return {
        "query": query,
        "intents": intents,
        "params": params,
        "routing": routing,
        "is_multi_agent": bool(routing["data_agent"]) and bool(routing["support_agent"]),
        "priority": "HIGH" if "urgent" in intents or "billing" in intents else "NORMAL"
    }


# =============================================================================
# Agent Executor
# =============================================================================

class RouterAgentExecutor(AgentExecutor):
    """Router agent executor that coordinates other agents."""
    
    async def execute(self, context: RequestContext, event_queue: asyncio.Queue) -> None:
        """Execute router logic - analyze and route to appropriate agents."""
        
        task = context.current_task
        query = context.message
        
        # Extract text
        if hasattr(query, 'parts') and query.parts:
            text = query.parts[0].text if hasattr(query.parts[0], 'text') else str(query.parts[0])
        else:
            text = str(query)
        
        print(f"\n📥 Router Agent received: {text}")
        
        # Analyze intent
        analysis = analyze_intent(text)
        print(f"🎯 Intent Analysis: {analysis['intents']}")
        print(f"   Routing: {analysis['routing']}")
        
        # Route to appropriate agent(s) via A2A
        responses = []
        
        # Route to Customer Data Agent
        if analysis["routing"]["data_agent"]:
            print(f"📤 Routing to Customer Data Agent...")
            response = await data_agent_client.send_task(text)
            responses.append(("Customer Data Agent", response))
        
        # Route to Support Agent
        if analysis["routing"]["support_agent"]:
            print(f"📤 Routing to Support Agent...")
            response = await support_agent_client.send_task(text)
            responses.append(("Support Agent", response))
        
        # Synthesize response
        final_response = self._synthesize_response(text, analysis, responses)
        
        print(f"📤 Router Agent final response: {final_response[:200]}...")
        
        # Create response
        artifact = Artifact(parts=[TextPart(text=final_response)])
        task.status = TaskStatus(state=TaskState.COMPLETED)
        task.artifacts = [artifact]
        
        await event_queue.put(task)
    
    async def cancel(self, context: RequestContext, event_queue: asyncio.Queue) -> None:
        raise NotImplementedError("Cancel not implemented")
    
    def _synthesize_response(self, query: str, analysis: dict, responses: list) -> str:
        """Synthesize final response from agent responses."""
        
        result = f"🔀 Router Agent Analysis\n"
        result += f"{'='*50}\n"
        result += f"Query: \"{query}\"\n"
        result += f"Detected Intents: {analysis['intents']}\n"
        result += f"Priority: {analysis['priority']}\n"
        result += f"Parameters: {analysis['params']}\n\n"
        
        if analysis["is_multi_agent"]:
            result += "📋 Multi-Agent Coordination\n"
            result += f"{'─'*50}\n"
        
        for agent_name, response in responses:
            result += f"\n🤖 Response from {agent_name}:\n"
            result += f"{'─'*50}\n"
            
            # Extract text from A2A response
            if "error" in response:
                result += f"❌ Error: {response['error']}\n"
            elif "result" in response:
                res = response["result"]
                if "artifacts" in res and res["artifacts"]:
                    for artifact in res["artifacts"]:
                        if "parts" in artifact:
                            for part in artifact["parts"]:
                                if "text" in part:
                                    result += part["text"] + "\n"
                elif "status" in res:
                    result += f"Status: {res['status']}\n"
            else:
                result += json.dumps(response, indent=2, default=str)[:500] + "\n"
        
        return result


# =============================================================================
# A2A Server Setup
# =============================================================================

def create_a2a_app():
    """Create the A2A Starlette application."""
    
    task_store = InMemoryTaskStore()
    agent_executor = RouterAgentExecutor()
    
    request_handler = DefaultRequestHandler(
        agent_card=AGENT_CARD,
        task_store=task_store,
        agent_executor=agent_executor
    )
    
    async def agent_card_handler(request):
        return JSONResponse(AGENT_CARD.model_dump(exclude_none=True))
    
    async def a2a_handler(request):
        body = await request.json()
        response = await request_handler.handle_request(body)
        return JSONResponse(response)
    
    async def health_handler(request):
        """Check health of subordinate agents."""
        data_card = await data_agent_client.get_agent_card()
        support_card = await support_agent_client.get_agent_card()
        
        return JSONResponse({
            "router": "online",
            "data_agent": "online" if "error" not in data_card else data_card["error"],
            "support_agent": "online" if "error" not in support_card else support_card["error"]
        })
    
    app = Starlette(
        routes=[
            Route("/.well-known/agent.json", agent_card_handler, methods=["GET"]),
            Route("/", a2a_handler, methods=["POST"]),
            Route("/health", health_handler, methods=["GET"]),
        ]
    )
    
    return app


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 ROUTER AGENT - ORCHESTRATOR (A2A Server)")
    print("="*60)
    print("\nStarting A2A server...")
    print("URL: http://localhost:8003")
    print("Agent Card: http://localhost:8003/.well-known/agent.json")
    print("\nSubordinate Agents (via A2A):")
    print("  • Customer Data Agent: http://localhost:8001")
    print("  • Support Agent: http://localhost:8002")
    print("\nSkills:")
    for skill in AGENT_CARD.skills:
        print(f"  • {skill.name}: {skill.description}")
    print("="*60)
    print("\nPress Ctrl+C to stop\n")
    
    app = create_a2a_app()
    uvicorn.run(app, host="0.0.0.0", port=8003)
