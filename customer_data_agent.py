"""
Customer Data Agent - A2A Agent using Google ADK
=================================================
This agent accesses customer data via the MCP server.
It exposes an A2A interface with proper Agent Card.

To run:
    python customer_data_agent.py
    
Agent will be available at: http://localhost:8001
Agent Card at: http://localhost:8001/.well-known/agent.json
"""

import os
import json
import asyncio
import httpx
from typing import Optional
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from mcp import ClientSession
from mcp.client.sse import sse_client

# MCP Server URL
MCP_SERVER_URL = "http://localhost:8000/sse"


class MCPClientWrapper:
    """Wrapper for MCP client to call tools on the MCP server."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self._session = None
        self._streams = None
    
    async def connect(self):
        """Connect to MCP server."""
        self._streams = sse_client(self.server_url)
        read_stream, write_stream = await self._streams.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()
        print(f"Connected to MCP server at {self.server_url}")
    
    async def disconnect(self):
        """Disconnect from MCP server."""
        if self._session:
            await self._session.__aexit__(None, None, None)
        if self._streams:
            await self._streams.__aexit__(None, None, None)
    
    async def list_tools(self):
        """List available tools from MCP server."""
        if not self._session:
            await self.connect()
        result = await self._session.list_tools()
        return result.tools
    
    async def call_tool(self, tool_name: str, arguments: dict):
        """Call a tool on the MCP server."""
        if not self._session:
            await self.connect()
        result = await self._session.call_tool(tool_name, arguments)
        # Parse the result content
        if result.content:
            for content in result.content:
                if hasattr(content, 'text'):
                    return json.loads(content.text)
        return {"error": "No result returned"}


# Global MCP client instance
mcp_client = MCPClientWrapper(MCP_SERVER_URL)


# ==================== Tool Functions for ADK Agent ====================

async def get_customer(customer_id: int) -> dict:
    """
    Get customer information by ID from the database via MCP.
    
    Args:
        customer_id: The unique identifier of the customer
        
    Returns:
        Customer data including id, name, email, phone, status
    """
    return await mcp_client.call_tool("get_customer", {"customer_id": customer_id})


async def list_customers(status: str = None, limit: int = 10) -> dict:
    """
    List customers with optional status filter.
    
    Args:
        status: Filter by 'active' or 'disabled' (optional)
        limit: Maximum number of customers (default 10)
        
    Returns:
        List of customers
    """
    args = {"limit": limit}
    if status:
        args["status"] = status
    return await mcp_client.call_tool("list_customers", args)


async def update_customer(customer_id: int, email: str = None, 
                         phone: str = None, name: str = None) -> dict:
    """
    Update customer information.
    
    Args:
        customer_id: The customer ID to update
        email: New email address (optional)
        phone: New phone number (optional)
        name: New name (optional)
        
    Returns:
        Updated customer data
    """
    args = {"customer_id": customer_id}
    if email:
        args["email"] = email
    if phone:
        args["phone"] = phone
    if name:
        args["name"] = name
    return await mcp_client.call_tool("update_customer", args)


async def get_customer_history(customer_id: int) -> dict:
    """
    Get ticket history for a customer.
    
    Args:
        customer_id: The customer ID
        
    Returns:
        Customer info and ticket history with statistics
    """
    return await mcp_client.call_tool("get_customer_history", {"customer_id": customer_id})


async def create_ticket(customer_id: int, issue: str, priority: str = "medium") -> dict:
    """
    Create a new support ticket for a customer.
    
    Args:
        customer_id: The customer ID
        issue: Description of the issue
        priority: 'low', 'medium', or 'high' (default: medium)
        
    Returns:
        Created ticket data
    """
    return await mcp_client.call_tool("create_ticket", {
        "customer_id": customer_id,
        "issue": issue,
        "priority": priority
    })


async def get_active_customers_with_open_tickets() -> dict:
    """
    Get all active customers who have open tickets.
    
    Returns:
        List of active customers with their open tickets
    """
    return await mcp_client.call_tool("get_active_customers_with_open_tickets", {})


# ==================== ADK Agent Definition ====================

# Create the Customer Data Agent
customer_data_agent = Agent(
    name="customer_data_agent",
    model="gemini-2.0-flash",
    description="Specialist agent for accessing and managing customer data via MCP. "
                "Can retrieve customer information, update records, view ticket history, "
                "and create support tickets.",
    instruction="""You are the Customer Data Agent, a specialist in customer data operations.
    
Your responsibilities:
1. Retrieve customer information by ID
2. List and filter customers by status
3. Update customer records (email, phone, name)
4. View customer ticket history
5. Create new support tickets
6. Report on active customers with open tickets

When a request comes in:
1. Identify what data operation is needed
2. Use the appropriate tool to access/modify data via MCP
3. Return the results clearly formatted

Always verify customer IDs exist before performing operations.
Handle errors gracefully and report them clearly.
""",
    tools=[
        get_customer,
        list_customers,
        update_customer,
        get_customer_history,
        create_ticket,
        get_active_customers_with_open_tickets
    ]
)


# ==================== A2A Server Setup ====================

def create_agent_card():
    """Create the A2A Agent Card for this agent."""
    return {
        "name": "customer_data_agent",
        "description": "Customer Data Agent - Accesses customer database via MCP",
        "version": "1.0.0",
        "url": "http://localhost:8001",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False
        },
        "skills": [
            {
                "id": "get_customer",
                "name": "Get Customer",
                "description": "Retrieve customer information by ID"
            },
            {
                "id": "list_customers", 
                "name": "List Customers",
                "description": "List customers with optional filters"
            },
            {
                "id": "update_customer",
                "name": "Update Customer",
                "description": "Update customer information"
            },
            {
                "id": "get_customer_history",
                "name": "Get Customer History",
                "description": "Get ticket history for a customer"
            },
            {
                "id": "create_ticket",
                "name": "Create Ticket",
                "description": "Create a new support ticket"
            },
            {
                "id": "get_active_customers_with_open_tickets",
                "name": "Get Active Customers with Open Tickets",
                "description": "Get all active customers who have open tickets"
            }
        ],
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"]
    }


async def run_agent_with_a2a():
    """Run the agent with A2A interface using ADK's to_a2a."""
    from google.adk.a2a import to_a2a
    import uvicorn
    
    # Connect to MCP server first
    print("Connecting to MCP server...")
    await mcp_client.connect()
    
    # Create A2A app from the agent
    a2a_app = to_a2a(customer_data_agent, port=8001)
    
    print("="*60)
    print("Customer Data Agent (A2A)")
    print("="*60)
    print(f"Agent URL: http://localhost:8001")
    print(f"Agent Card: http://localhost:8001/.well-known/agent.json")
    print("="*60)
    
    # Run with uvicorn
    config = uvicorn.Config(a2a_app, host="0.0.0.0", port=8001, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("Warning: GOOGLE_API_KEY not set. Set it in .env file or environment.")
        print("export GOOGLE_API_KEY=your_api_key_here")
    
    asyncio.run(run_agent_with_a2a())
