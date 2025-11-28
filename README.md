# Multi-Agent Customer Service System with A2A and MCP

A multi-agent customer service system implementing:
- **MCP (Model Context Protocol)**: For database tool access via SSE transport
- **A2A (Agent-to-Agent Protocol)**: For inter-agent communication with Agent Cards

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Customer Query                               │
└────────────────────────────────────┬────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ROUTER AGENT (Port 8003)                          │
│                    A2A Orchestrator                                  │
│  • Receives queries                                                  │
│  • Analyzes intent                                                   │
│  • Routes via A2A to specialists                                     │
│  • Agent Card: /.well-known/agent.json                              │
└──────────────────┬────────────────────────┬─────────────────────────┘
                   │ A2A                    │ A2A
                   ▼                        ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│   CUSTOMER DATA AGENT        │  │      SUPPORT AGENT               │
│   (Port 8001)                │  │      (Port 8002)                 │
│   A2A Agent                  │  │      A2A Agent                   │
│  • MCP database access       │  │  • Billing issues                │
│  • Get/update customers      │  │  • Cancellations                 │
│  • Ticket management         │  │  • Upgrades                      │
│  • Agent Card available      │  │  • Escalations                   │
└────────────────┬─────────────┘  └──────────────────────────────────┘
                 │ MCP (SSE)
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MCP SERVER (Port 8000)                          │
│  Transport: SSE (Server-Sent Events)                                │
│  Endpoint: http://localhost:8000/sse                                │
│  Tools: get_customer, list_customers, update_customer,              │
│         create_ticket, get_customer_history, etc.                   │
│  Testable via: MCP Inspector                                        │
└────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SQLite Database (support.db)                      │
│  Tables: customers, tickets                                          │
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Setup Instructions

### Prerequisites
- Python 3.10 or higher
- Google API Key (for Gemini model in ADK agents)

### Step 1: Clone and Setup Environment

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/multi-agent-customer-service.git
cd multi-agent-customer-service

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Mac/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Set API Key

```bash
# Create .env file
echo "GOOGLE_API_KEY=your_api_key_here" > .env

# Or export directly
export GOOGLE_API_KEY=your_api_key_here
```

Get your API key from: https://aistudio.google.com/app/apikey

### Step 3: Run the System

Open 4 terminal windows and run each component:

**Terminal 1 - MCP Server:**
```bash
python mcp_server.py
# Server runs at http://localhost:8000/sse
```

**Terminal 2 - Customer Data Agent:**
```bash
python customer_data_agent.py
# Agent runs at http://localhost:8001
# Agent Card at http://localhost:8001/.well-known/agent.json
```

**Terminal 3 - Support Agent:**
```bash
python support_agent.py
# Agent runs at http://localhost:8002
# Agent Card at http://localhost:8002/.well-known/agent.json
```

**Terminal 4 - Router Agent:**
```bash
python router_agent.py
# Agent runs at http://localhost:8003
# Agent Card at http://localhost:8003/.well-known/agent.json
```

### Step 4: Run Demo

```bash
python main.py
```

## 🧪 Testing

### Test MCP Server with MCP Inspector

```bash
# Install MCP Inspector
npx @modelcontextprotocol/inspector

# In the inspector UI, connect to:
# http://localhost:8000/sse

# Test tools:
# - tools/list (lists all available tools)
# - tools/call with get_customer {"customer_id": 5}
```

### Test A2A Agents

```bash
# View Agent Cards
curl http://localhost:8001/.well-known/agent.json  # Customer Data Agent
curl http://localhost:8002/.well-known/agent.json  # Support Agent
curl http://localhost:8003/.well-known/agent.json  # Router Agent

# Or use A2A Inspector at: https://a2a-inspector.vercel.app/
```

## 📁 Project Structure

```
multi-agent-customer-service/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .env                         # API keys (create this)
├── mcp_server.py               # MCP Server with SSE transport
├── customer_data_agent.py      # A2A Agent for data operations
├── support_agent.py            # A2A Agent for support operations
├── router_agent.py             # A2A Orchestrator agent
├── main.py                     # Demo runner
└── support.db                  # SQLite database (auto-created)
```

## 🔧 MCP Tools Implemented

| Tool | Description | MCP Endpoint |
|------|-------------|--------------|
| `get_customer` | Get customer by ID | tools/call |
| `list_customers` | List customers with filters | tools/call |
| `update_customer` | Update customer info | tools/call |
| `create_ticket` | Create support ticket | tools/call |
| `get_customer_history` | Get customer's tickets | tools/call |
| `get_tickets_by_priority` | Filter tickets by priority | tools/call |
| `get_active_customers_with_open_tickets` | Report query | tools/call |

## 🤖 A2A Agent Cards

Each agent exposes capabilities via `/.well-known/agent.json`:

### Router Agent (Port 8003)
- Skills: analyze_intent, route_to_data_agent, route_to_support_agent, coordinate_multi_agent

### Customer Data Agent (Port 8001)
- Skills: get_customer, list_customers, update_customer, get_customer_history, create_ticket

### Support Agent (Port 8002)
- Skills: handle_billing, handle_cancellation, handle_upgrade, handle_urgent, general_support

## 🎯 Test Scenarios

1. **Simple Query**: `"Get customer information for ID 5"`
2. **Coordinated Query**: `"I'm customer 1 and need help upgrading my account"`
3. **Complex Query**: `"Show me all active customers who have open tickets"`
4. **Escalation**: `"I've been charged twice, please refund immediately!"`
5. **Multi-Intent**: `"Update my email to new@email.com and show my ticket history for customer ID 2"`

## 📝 Conclusion

This project demonstrates:
- **MCP Protocol**: Proper implementation with SSE transport, testable via MCP Inspector
- **A2A Protocol**: Agents with proper Agent Cards, task-based communication
- **Multi-Agent Coordination**: Router orchestrates specialists for complex queries
- **Separation of Concerns**: Data access via MCP, agent logic via ADK, coordination via A2A

## 📚 References

- [MCP Specification](https://modelcontextprotocol.io/)
- [A2A Protocol](https://a2aprotocol.ai/)
- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## 👤 Author

[Your Name]  
[Your Course/Class]
