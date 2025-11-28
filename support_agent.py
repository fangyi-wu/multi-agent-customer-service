"""
Support Agent - A2A Agent using Google ADK
===========================================
This agent handles customer support queries, billing, cancellations, and escalations.
It exposes an A2A interface with proper Agent Card.

To run:
    python support_agent.py
    
Agent will be available at: http://localhost:8002
Agent Card at: http://localhost:8002/.well-known/agent.json
"""

import os
import asyncio
from typing import Optional
from google.adk.agents import Agent


# ==================== Support Tool Functions ====================

def handle_billing_issue(issue_description: str, is_urgent: bool = False) -> dict:
    """
    Handle a billing-related customer issue.
    
    Args:
        issue_description: Description of the billing issue
        is_urgent: Whether this is an urgent issue (double charge, fraud, etc.)
        
    Returns:
        Response with handling steps and resolution timeline
    """
    urgent_keywords = ["charged twice", "double charge", "refund", "unauthorized", "fraud"]
    is_urgent = is_urgent or any(kw in issue_description.lower() for kw in urgent_keywords)
    
    return {
        "success": True,
        "issue_type": "billing",
        "is_urgent": is_urgent,
        "message": "I understand you have a billing concern. Let me help you with that.",
        "handling_steps": [
            "Reviewing billing history",
            "Checking for discrepancies",
            "Initiating resolution process if needed"
        ],
        "escalation_required": is_urgent,
        "estimated_resolution": "4-8 hours" if is_urgent else "24-48 hours",
        "priority": "HIGH" if is_urgent else "NORMAL"
    }


def handle_cancellation_request(reason: str = None) -> dict:
    """
    Handle a subscription/account cancellation request.
    
    Args:
        reason: Reason for cancellation (optional)
        
    Returns:
        Response with retention offers and next steps
    """
    return {
        "success": True,
        "issue_type": "cancellation",
        "message": "I'm sorry to hear you're considering cancellation.",
        "retention_offers": [
            "Would you like to discuss any concerns before canceling?",
            "We can offer a 30-day pause instead of full cancellation",
            "There may be a plan that better fits your needs"
        ],
        "next_steps": [
            "Please confirm your cancellation request",
            "You'll receive a confirmation email",
            "Any remaining credits will be applied to your final bill"
        ],
        "requires_confirmation": True,
        "reason_provided": reason
    }


def handle_upgrade_request(current_tier: str = "standard") -> dict:
    """
    Handle an account upgrade request.
    
    Args:
        current_tier: Customer's current subscription tier
        
    Returns:
        Available upgrade options and promotions
    """
    return {
        "success": True,
        "issue_type": "upgrade",
        "current_tier": current_tier,
        "message": "Great! I can help you upgrade your account.",
        "available_upgrades": [
            {
                "tier": "Premium",
                "price": "$19.99/mo",
                "features": ["Priority support", "Extended storage", "Advanced analytics"]
            },
            {
                "tier": "Enterprise", 
                "price": "$49.99/mo",
                "features": ["24/7 support", "Unlimited storage", "Custom integrations", "Dedicated account manager"]
            }
        ],
        "current_promotion": "Upgrade now and get 20% off your first 3 months!"
    }


def handle_urgent_issue(issue_description: str, customer_id: int = None) -> dict:
    """
    Handle an urgent/emergency support issue.
    
    Args:
        issue_description: Description of the urgent issue
        customer_id: Customer ID if available
        
    Returns:
        Urgent response with escalation path
    """
    return {
        "success": True,
        "issue_type": "urgent",
        "priority": "HIGH",
        "message": "I understand this is urgent. I'm escalating this immediately.",
        "escalation_path": [
            "Issue logged as HIGH priority",
            "Escalated to senior support team",
            "You will receive a callback within 2 hours"
        ],
        "immediate_actions": [
            "Please don't worry, we're on it",
            "A senior team member will contact you shortly",
            "Reference your ticket number for follow-up"
        ],
        "customer_id": customer_id,
        "issue_summary": issue_description[:100]
    }


def provide_general_support(query: str) -> dict:
    """
    Provide general customer support assistance.
    
    Args:
        query: The customer's support query
        
    Returns:
        General support response with options
    """
    return {
        "success": True,
        "issue_type": "general_support",
        "message": "Hello! I'm here to help you today.",
        "available_assistance": [
            "View your account information",
            "Check ticket history",
            "Report a new issue",
            "Billing questions",
            "Account upgrades",
            "Technical support"
        ],
        "query_received": query,
        "next_action": "Please let me know what specific help you need."
    }


def analyze_support_request(request: str) -> dict:
    """
    Analyze a support request to determine type and priority.
    
    Args:
        request: The customer's support request text
        
    Returns:
        Analysis of request type, priority, and recommended handling
    """
    request_lower = request.lower()
    
    # Determine request type
    if any(word in request_lower for word in ["billing", "charge", "invoice", "payment", "refund"]):
        request_type = "billing"
    elif any(word in request_lower for word in ["cancel", "cancellation", "stop", "terminate"]):
        request_type = "cancellation"
    elif any(word in request_lower for word in ["upgrade", "premium", "better plan"]):
        request_type = "upgrade"
    elif any(word in request_lower for word in ["urgent", "emergency", "asap", "immediately", "down", "broken"]):
        request_type = "urgent"
    else:
        request_type = "general"
    
    # Determine priority
    if any(word in request_lower for word in ["urgent", "immediately", "asap", "emergency", "charged twice", "fraud"]):
        priority = "HIGH"
    elif any(word in request_lower for word in ["broken", "not working", "error", "failed"]):
        priority = "MEDIUM"
    else:
        priority = "LOW"
    
    return {
        "success": True,
        "original_request": request,
        "detected_type": request_type,
        "priority": priority,
        "recommended_handler": f"handle_{request_type}_issue" if request_type != "general" else "provide_general_support",
        "keywords_found": [word for word in ["billing", "cancel", "upgrade", "urgent", "refund"] 
                          if word in request_lower]
    }


# ==================== ADK Agent Definition ====================

support_agent = Agent(
    name="support_agent",
    model="gemini-2.0-flash",
    description="Specialist agent for customer support operations. "
                "Handles billing issues, cancellations, upgrades, urgent issues, "
                "and general support queries.",
    instruction="""You are the Support Agent, a specialist in customer support operations.

Your responsibilities:
1. Analyze incoming support requests to determine type and priority
2. Handle billing issues (charges, refunds, invoice questions)
3. Process cancellation requests with retention offers
4. Assist with account upgrades
5. Escalate urgent/emergency issues appropriately
6. Provide general support assistance

When handling a request:
1. First analyze the request to understand type and priority
2. Use the appropriate handler function
3. Provide clear, helpful responses
4. Escalate when necessary
5. Always be empathetic and professional

For urgent issues (mentions of "charged twice", "fraud", "emergency", "down"):
- Immediately mark as HIGH priority
- Initiate escalation process
- Provide immediate acknowledgment
""",
    tools=[
        handle_billing_issue,
        handle_cancellation_request,
        handle_upgrade_request,
        handle_urgent_issue,
        provide_general_support,
        analyze_support_request
    ]
)


# ==================== A2A Server Setup ====================

def create_agent_card():
    """Create the A2A Agent Card for this agent."""
    return {
        "name": "support_agent",
        "description": "Support Agent - Handles customer support, billing, cancellations, and escalations",
        "version": "1.0.0",
        "url": "http://localhost:8002",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False
        },
        "skills": [
            {
                "id": "handle_billing",
                "name": "Handle Billing Issue",
                "description": "Process billing-related customer issues"
            },
            {
                "id": "handle_cancellation",
                "name": "Handle Cancellation",
                "description": "Process subscription/account cancellation requests"
            },
            {
                "id": "handle_upgrade",
                "name": "Handle Upgrade",
                "description": "Process account upgrade requests"
            },
            {
                "id": "handle_urgent",
                "name": "Handle Urgent Issue",
                "description": "Process urgent/emergency support issues"
            },
            {
                "id": "general_support",
                "name": "General Support",
                "description": "Provide general customer support"
            },
            {
                "id": "analyze_request",
                "name": "Analyze Request",
                "description": "Analyze support request type and priority"
            }
        ],
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"]
    }


async def run_agent_with_a2a():
    """Run the agent with A2A interface using ADK's to_a2a."""
    from google.adk.a2a import to_a2a
    import uvicorn
    
    # Create A2A app from the agent
    a2a_app = to_a2a(support_agent, port=8002)
    
    print("="*60)
    print("Support Agent (A2A)")
    print("="*60)
    print(f"Agent URL: http://localhost:8002")
    print(f"Agent Card: http://localhost:8002/.well-known/agent.json")
    print("="*60)
    
    # Run with uvicorn
    config = uvicorn.Config(a2a_app, host="0.0.0.0", port=8002, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("Warning: GOOGLE_API_KEY not set. Set it in .env file or environment.")
        print("export GOOGLE_API_KEY=your_api_key_here")
    
    asyncio.run(run_agent_with_a2a())
