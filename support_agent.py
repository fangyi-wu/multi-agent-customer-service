"""
Support Agent - A2A Server
==========================
An A2A-compliant agent that handles customer support operations.
Uses the a2a-python SDK directly - NO external LLM API required.

To run:
    python support_agent.py

Agent will be available at:
    - A2A endpoint: http://localhost:8002
    - Agent Card: http://localhost:8002/.well-known/agent.json
"""

import json
import asyncio
from typing import Any

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
    name="support_agent",
    description="Support Agent - Handles customer support operations including "
                "billing issues, cancellations, upgrades, and urgent issues.",
    url="http://localhost:8002",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=False, pushNotifications=False),
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
    skills=[
        AgentSkill(
            id="handle_billing",
            name="Handle Billing",
            description="Handle billing-related issues and refunds"
        ),
        AgentSkill(
            id="handle_cancellation",
            name="Handle Cancellation",
            description="Process cancellation requests with retention offers"
        ),
        AgentSkill(
            id="handle_upgrade",
            name="Handle Upgrade",
            description="Assist with account upgrades"
        ),
        AgentSkill(
            id="handle_urgent",
            name="Handle Urgent",
            description="Escalate and handle urgent/emergency issues"
        ),
        AgentSkill(
            id="general_support",
            name="General Support",
            description="Provide general customer support assistance"
        )
    ]
)


# =============================================================================
# Support Functions
# =============================================================================

def handle_billing_issue(issue: str) -> dict:
    """Handle billing-related issues."""
    urgent_keywords = ["charged twice", "double charge", "refund", "fraud", "unauthorized"]
    is_urgent = any(kw in issue.lower() for kw in urgent_keywords)
    
    return {
        "type": "billing",
        "is_urgent": is_urgent,
        "priority": "HIGH" if is_urgent else "NORMAL",
        "message": "I understand you have a billing concern.",
        "actions": [
            "Reviewing your billing history",
            "Checking for discrepancies",
            "Initiating resolution process"
        ],
        "escalated": is_urgent,
        "resolution_time": "4-8 hours" if is_urgent else "24-48 hours"
    }


def handle_cancellation_request(reason: str = None) -> dict:
    """Handle cancellation requests."""
    return {
        "type": "cancellation",
        "message": "I'm sorry to hear you're considering cancellation.",
        "retention_offers": [
            "30-day pause instead of cancellation",
            "Discounted plan at 50% off",
            "Free upgrade to premium for 1 month"
        ],
        "steps": [
            "Please confirm your cancellation request",
            "Review any remaining credits",
            "Receive confirmation within 24 hours"
        ],
        "requires_confirmation": True
    }


def handle_upgrade_request(current_tier: str = "standard") -> dict:
    """Handle upgrade requests."""
    return {
        "type": "upgrade",
        "message": "Great choice! I can help you upgrade.",
        "options": [
            {"tier": "Premium", "price": "$19.99/month", "features": ["Priority support", "100GB storage"]},
            {"tier": "Enterprise", "price": "$49.99/month", "features": ["24/7 support", "Unlimited storage", "Dedicated manager"]}
        ],
        "promotion": "🎉 20% off first 3 months if you upgrade today!",
        "next_steps": "Would you like me to process an upgrade?"
    }


def handle_urgent_issue(issue: str) -> dict:
    """Handle urgent issues with immediate escalation."""
    return {
        "type": "urgent",
        "priority": "HIGH",
        "message": "⚠️ I understand this is urgent. Escalating immediately!",
        "actions": [
            "✓ Issue logged as HIGH priority",
            "✓ Escalated to senior support team",
            "✓ You will receive a callback within 2 hours",
            "✓ Case manager assigned"
        ],
        "ticket_created": True,
        "callback_scheduled": True
    }


def provide_general_support(query: str) -> dict:
    """Provide general support assistance."""
    return {
        "type": "general",
        "message": "Hello! I'm here to help.",
        "available_assistance": [
            "Account settings and profile",
            "Billing and payments",
            "Technical support",
            "Feature requests",
            "Account upgrades"
        ],
        "next_action": "How can I assist you specifically?"
    }


# =============================================================================
# Agent Executor
# =============================================================================

class SupportAgentExecutor(AgentExecutor):
    """Agent executor for support operations."""
    
    async def execute(self, context: RequestContext, event_queue: asyncio.Queue) -> None:
        """Execute support agent logic."""
        
        task = context.current_task
        query = context.message
        
        # Extract text
        if hasattr(query, 'parts') and query.parts:
            text = query.parts[0].text if hasattr(query.parts[0], 'text') else str(query.parts[0])
        else:
            text = str(query)
        
        print(f"\n📥 Support Agent received: {text}")
        
        # Process and respond
        response_text = self._process_query(text)
        
        print(f"📤 Support Agent response: {response_text[:200]}...")
        
        # Create response
        artifact = Artifact(parts=[TextPart(text=response_text)])
        task.status = TaskStatus(state=TaskState.COMPLETED)
        task.artifacts = [artifact]
        
        await event_queue.put(task)
    
    async def cancel(self, context: RequestContext, event_queue: asyncio.Queue) -> None:
        raise NotImplementedError("Cancel not implemented")
    
    def _process_query(self, text: str) -> str:
        """Process query and return support response."""
        text_lower = text.lower()
        
        try:
            # Urgent issues - check first
            if any(w in text_lower for w in ["urgent", "immediately", "asap", "emergency", "down"]):
                result = handle_urgent_issue(text)
                response = f"🚨 {result['message']}\n\n"
                response += "Actions taken:\n"
                for action in result['actions']:
                    response += f"  {action}\n"
                return response
            
            # Billing issues
            elif any(w in text_lower for w in ["billing", "charge", "refund", "invoice", "payment"]):
                result = handle_billing_issue(text)
                response = f"💳 Billing Support\n\n{result['message']}\n\n"
                response += f"Priority: {result['priority']}\n"
                response += f"Estimated Resolution: {result['resolution_time']}\n\n"
                response += "We will:\n"
                for action in result['actions']:
                    response += f"  • {action}\n"
                if result['escalated']:
                    response += "\n⚠️ This has been escalated to our billing specialists."
                return response
            
            # Cancellation
            elif any(w in text_lower for w in ["cancel", "cancellation", "stop", "terminate"]):
                result = handle_cancellation_request()
                response = f"📝 Cancellation Request\n\n{result['message']}\n\n"
                response += "Before you go, consider these offers:\n"
                for offer in result['retention_offers']:
                    response += f"  🎁 {offer}\n"
                response += "\nNext steps:\n"
                for step in result['steps']:
                    response += f"  • {step}\n"
                return response
            
            # Upgrade
            elif any(w in text_lower for w in ["upgrade", "premium", "better plan"]):
                result = handle_upgrade_request()
                response = f"⬆️ Upgrade Options\n\n{result['message']}\n\n"
                response += f"{result['promotion']}\n\n"
                response += "Available plans:\n"
                for option in result['options']:
                    response += f"\n📦 {option['tier']} - {option['price']}\n"
                    for feature in option['features']:
                        response += f"    ✓ {feature}\n"
                return response
            
            # General support
            else:
                result = provide_general_support(text)
                response = f"👋 {result['message']}\n\n"
                response += "I can help you with:\n"
                for item in result['available_assistance']:
                    response += f"  • {item}\n"
                response += f"\n{result['next_action']}"
                return response
        
        except Exception as e:
            return f"Error processing support request: {str(e)}"


# =============================================================================
# A2A Server Setup
# =============================================================================

def create_a2a_app():
    """Create the A2A Starlette application."""
    
    task_store = InMemoryTaskStore()
    agent_executor = SupportAgentExecutor()
    
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
    
    app = Starlette(
        routes=[
            Route("/.well-known/agent.json", agent_card_handler, methods=["GET"]),
            Route("/", a2a_handler, methods=["POST"]),
        ]
    )
    
    return app


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 SUPPORT AGENT (A2A Server)")
    print("="*60)
    print("\nStarting A2A server...")
    print("URL: http://localhost:8002")
    print("Agent Card: http://localhost:8002/.well-known/agent.json")
    print("\nSkills:")
    for skill in AGENT_CARD.skills:
        print(f"  • {skill.name}: {skill.description}")
    print("="*60)
    print("\nPress Ctrl+C to stop\n")
    
    app = create_a2a_app()
    uvicorn.run(app, host="0.0.0.0", port=8002)
