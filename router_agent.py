"""
Router Agent (Orchestrator) - A2A Agent using Google ADK
=========================================================
This is the main orchestrator agent that:
- Receives customer queries
- Analyzes intent
- Routes to appropriate specialist agents via A2A
- Coordinates responses from multiple agents

To run:
    python router_agent.py
    
Agent will be available at: http://localhost:8003
Agent Card at: http://localhost:8003/.well-known/agent.json

Prerequisites:
    1. MCP Server running at localhost:8000
    2. Customer Data Agent running at localhost:8001
    3. Support Agent running at localhost:8002
"""

import os
import re
import json
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool


# ==================== A2A Client for Remote Agents ====================

class A2AClient:
    """Client for communicating with remote A2A agents."""
    
    def __init__(self, agent_url: str):
        self.agent_url = agent_url.rstrip('/')
        self.agent_card = None
    
    async def get_agent_card(self) -> dict:
        """Fetch the agent card from the remote agent."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.agent_url}/.well-known/agent.json")
            if response.status_code == 200:
                self.agent_card = response.json()
                return self.agent_card
            raise Exception(f"Failed to get agent card: {response.status_code}")
    
    async def send_task(self, message: str, task_id: str = None) -> dict:
        """Send a task to the remote agent via A2A protocol."""
        if not task_id:
            import uuid
            task_id = str(uuid.uuid4())
        
        # A2A Task Request format
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
            response = await client.post(
                f"{self.agent_url}",
                json=request,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                return response.json()
            return {"error": f"Request failed: {response.status_code}", "body": response.text}


# Remote agent clients
customer_data_client = A2AClient("http://localhost:8001")
support_client = A2AClient("http://localhost:8002")


# ==================== Router Tool Functions ====================

def analyze_intent(query: str) -> dict:
    """
    Analyze the customer query to determine intent(s).
    
    Args:
        query: The customer's query text
        
    Returns:
        Detected intents, extracted parameters, and routing recommendation
    """
    query_lower = query.lower()
    intents = []
    params = {}
    
    # Detect intents
    intent_patterns = {
        "get_customer_info": [r"get customer", r"customer info", r"customer id \d+", r"who is customer"],
        "view_ticket_history": [r"ticket history", r"show.*tickets", r"my tickets", r"past.*tickets"],
        "update_customer": [r"update.*email", r"change.*email", r"update.*info", r"change.*phone"],
        "create_ticket": [r"new ticket", r"create.*ticket", r"report.*issue"],
        "billing_issue": [r"billing", r"charge", r"invoice", r"refund", r"charged twice"],
        "cancellation": [r"cancel", r"cancellation", r"close.*account"],
        "upgrade": [r"upgrade", r"premium", r"better plan"],
        "urgent": [r"urgent", r"emergency", r"immediately", r"asap", r"down", r"broken"],
        "report": [r"show.*all", r"active.*customers.*open.*tickets", r"report"]
    }
    
    for intent, patterns in intent_patterns.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                if intent not in intents:
                    intents.append(intent)
                break
    
    # Extract parameters
    id_match = re.search(r'(?:customer\s*(?:id|#)?|id)\s*(\d+)', query_lower)
    if id_match:
        params["customer_id"] = int(id_match.group(1))
    
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', query)
    if email_match:
        params["email"] = email_match.group()
    
    # Determine routing
    if not intents:
        intents.append("general_support")
    
    data_agent_intents = ["get_customer_info", "view_ticket_history", "update_customer", 
                         "create_ticket", "report"]
    support_agent_intents = ["billing_issue", "cancellation", "upgrade", "urgent", "general_support"]
    
    routing = []
    for intent in intents:
        if intent in data_agent_intents:
            routing.append({"intent": intent, "agent": "customer_data_agent"})
        if intent in support_agent_intents:
            routing.append({"intent": intent, "agent": "support_agent"})
    
    return {
        "success": True,
        "original_query": query,
        "detected_intents": intents,
        "extracted_parameters": params,
        "is_multi_intent": len(intents) > 1,
        "routing": routing,
        "priority": "HIGH" if "urgent" in intents or "billing_issue" in intents else "NORMAL"
    }


async def route_to_customer_data_agent(request: str) -> dict:
    """
    Route a request to the Customer Data Agent via A2A.
    
    Args:
        request: The request to send to the data agent
        
    Returns:
        Response from the Customer Data Agent
    """
    try:
        response = await customer_data_client.send_task(request)
        return {
            "success": True,
            "agent": "customer_data_agent",
            "response": response
        }
    except Exception as e:
        return {
            "success": False,
            "agent": "customer_data_agent",
            "error": str(e)
        }


async def route_to_support_agent(request: str) -> dict:
    """
    Route a request to the Support Agent via A2A.
    
    Args:
        request: The request to send to the support agent
        
    Returns:
        Response from the Support Agent
    """
    try:
        response = await support_client.send_task(request)
        return {
            "success": True,
            "agent": "support_agent",
            "response": response
        }
    except Exception as e:
        return {
            "success": False,
            "agent": "support_agent",
            "error": str(e)
        }


async def coordinate_multi_agent_request(query: str, intents: List[str], 
                                         params: Dict[str, Any]) -> dict:
    """
    Coordinate a request that requires multiple agents.
    
    Args:
        query: Original customer query
        intents: List of detected intents
        params: Extracted parameters
        
    Returns:
        Coordinated response from multiple agents
    """
    results = []
    
    # Determine which agents to call
    data_intents = [i for i in intents if i in ["get_customer_info", "view_ticket_history", 
                                                  "update_customer", "create_ticket", "report"]]
    support_intents = [i for i in intents if i in ["billing_issue", "cancellation", 
                                                     "upgrade", "urgent", "general_support"]]
    
    # Call Customer Data Agent if needed
    if data_intents:
        data_request = f"Handle these intents: {data_intents}. "
        if params.get("customer_id"):
            data_request += f"Customer ID: {params['customer_id']}. "
        if params.get("email"):
            data_request += f"New email: {params['email']}. "
        data_request += f"Original query: {query}"
        
        data_result = await route_to_customer_data_agent(data_request)
        results.append(data_result)
    
    # Call Support Agent if needed
    if support_intents:
        support_request = f"Handle these intents: {support_intents}. Original query: {query}"
        support_result = await route_to_support_agent(support_request)
        results.append(support_result)
    
    return {
        "success": True,
        "coordination_type": "multi_agent",
        "intents_processed": intents,
        "agents_called": len(results),
        "results": results
    }


def synthesize_response(agent_results: List[dict], original_query: str) -> dict:
    """
    Synthesize a final response from multiple agent results.
    
    Args:
        agent_results: List of results from various agents
        original_query: The original customer query
        
    Returns:
        Synthesized final response
    """
    successful_results = [r for r in agent_results if r.get("success")]
    failed_results = [r for r in agent_results if not r.get("success")]
    
    summary_parts = []
    for result in successful_results:
        agent = result.get("agent", "unknown")
        summary_parts.append(f"{agent}: processed successfully")
    
    return {
        "success": len(failed_results) == 0,
        "original_query": original_query,
        "agents_consulted": len(agent_results),
        "successful_responses": len(successful_results),
        "failed_responses": len(failed_results),
        "summary": " | ".join(summary_parts) if summary_parts else "No agents responded",
        "results": agent_results
    }


# ==================== ADK Router Agent Definition ====================

router_agent = Agent(
    name="router_agent",
    model="gemini-2.0-flash",
    description="Main orchestrator agent that receives customer queries, analyzes intent, "
                "and routes to appropriate specialist agents (Customer Data Agent, Support Agent) "
                "via A2A protocol. Coordinates multi-agent responses.",
    instruction="""You are the Router Agent, the main orchestrator of the customer service system.

Your responsibilities:
1. Receive customer queries
2. Analyze the query to detect intents and extract parameters
3. Route requests to appropriate specialist agents via A2A:
   - Customer Data Agent (localhost:8001): For data operations (get customer, list, update, history, tickets)
   - Support Agent (localhost:8002): For support operations (billing, cancellation, upgrade, urgent)
4. Coordinate responses from multiple agents when needed
5. Synthesize final responses

Processing Flow:
1. Use analyze_intent() to understand the query
2. Based on detected intents, route to appropriate agent(s)
3. For multi-intent queries, coordinate multiple agent calls
4. Synthesize results into a coherent response

Important:
- Always analyze intent first
- For data queries (customer info, tickets), route to Customer Data Agent
- For support queries (billing, help, urgent), route to Support Agent
- Handle multi-intent queries by coordinating both agents
- Escalate urgent issues immediately
""",
    tools=[
        analyze_intent,
        route_to_customer_data_agent,
        route_to_support_agent,
        coordinate_multi_agent_request,
        synthesize_response
    ]
)


# ==================== A2A Server Setup ====================

def create_agent_card():
    """Create the A2A Agent Card for the Router Agent."""
    return {
        "name": "router_agent",
        "description": "Router/Orchestrator Agent - Analyzes queries and coordinates specialist agents",
        "version": "1.0.0",
        "url": "http://localhost:8003",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False
        },
        "skills": [
            {
                "id": "analyze_intent",
                "name": "Analyze Intent",
                "description": "Analyze customer query to detect intents and parameters"
            },
            {
                "id": "route_to_data_agent",
                "name": "Route to Data Agent",
                "description": "Route request to Customer Data Agent via A2A"
            },
            {
                "id": "route_to_support_agent",
                "name": "Route to Support Agent", 
                "description": "Route request to Support Agent via A2A"
            },
            {
                "id": "coordinate_multi_agent",
                "name": "Coordinate Multi-Agent",
                "description": "Coordinate requests requiring multiple agents"
            },
            {
                "id": "synthesize_response",
                "name": "Synthesize Response",
                "description": "Synthesize final response from multiple agents"
            }
        ],
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "subordinateAgents": [
            {
                "name": "customer_data_agent",
                "url": "http://localhost:8001",
                "description": "Specialist for customer data operations"
            },
            {
                "name": "support_agent",
                "url": "http://localhost:8002",
                "description": "Specialist for customer support operations"
            }
        ]
    }


async def run_agent_with_a2a():
    """Run the router agent with A2A interface."""
    from google.adk.a2a import to_a2a
    import uvicorn
    
    # Create A2A app from the agent
    a2a_app = to_a2a(router_agent, port=8003)
    
    print("="*60)
    print("Router Agent (Orchestrator) - A2A")
    print("="*60)
    print(f"Agent URL: http://localhost:8003")
    print(f"Agent Card: http://localhost:8003/.well-known/agent.json")
    print("\nSubordinate Agents:")
    print(f"  - Customer Data Agent: http://localhost:8001")
    print(f"  - Support Agent: http://localhost:8002")
    print("="*60)
    
    # Run with uvicorn
    config = uvicorn.Config(a2a_app, host="0.0.0.0", port=8003, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("Warning: GOOGLE_API_KEY not set. Set it in .env file or environment.")
        print("export GOOGLE_API_KEY=your_api_key_here")
    
    asyncio.run(run_agent_with_a2a())
