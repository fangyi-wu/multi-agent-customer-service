"""
MCP Server for Customer Support System
======================================
A proper MCP server with SSE transport that can be tested with MCP Inspector.

To run:
    python mcp_server.py

To test with MCP Inspector:
    npx @modelcontextprotocol/inspector
    Connect to: http://localhost:8000/sse

Tools implemented:
    - get_customer(customer_id)
    - list_customers(status, limit)
    - update_customer(customer_id, email, phone, name, status)
    - create_ticket(customer_id, issue, priority)
    - get_customer_history(customer_id)
    - get_tickets_by_priority(priority, status)
    - get_active_customers_with_open_tickets()
"""

import sqlite3
import json
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# =============================================================================
# Database Setup
# =============================================================================

DB_PATH = "support.db"

def setup_database():
    """Initialize database with tables and sample data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create customers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create tickets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            issue TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)
    
    # Check if data exists
    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] == 0:
        # Insert sample customers
        customers = [
            ("John Doe", "john.doe@example.com", "+1-555-0101", "active"),
            ("Jane Smith", "jane.smith@example.com", "+1-555-0102", "active"),
            ("Bob Johnson", "bob.johnson@example.com", "+1-555-0103", "disabled"),
            ("Alice Williams", "alice.w@techcorp.com", "+1-555-0104", "active"),
            ("Charlie Brown", "charlie.brown@email.com", "+1-555-0105", "active"),
            ("Diana Prince", "diana.prince@company.org", "+1-555-0106", "active"),
            ("Edward Norton", "e.norton@business.net", "+1-555-0107", "active"),
        ]
        cursor.executemany(
            "INSERT INTO customers (name, email, phone, status) VALUES (?, ?, ?, ?)",
            customers
        )
        
        # Insert sample tickets
        tickets = [
            (1, "Cannot login to account", "open", "high"),
            (1, "Password reset not working", "in_progress", "medium"),
            (2, "Billing question about invoice", "resolved", "low"),
            (4, "Database connection timeout", "in_progress", "high"),
            (5, "Feature request: dark mode", "open", "low"),
            (6, "Dashboard loading slowly", "open", "medium"),
            (7, "Payment processing failing", "open", "high"),
        ]
        cursor.executemany(
            "INSERT INTO tickets (customer_id, issue, status, priority) VALUES (?, ?, ?, ?)",
            tickets
        )
        
        conn.commit()
        print("✅ Database initialized with sample data")
    else:
        print("✅ Database already exists")
    
    conn.close()

def get_db():
    """Get database connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# =============================================================================
# MCP Server Definition
# =============================================================================

mcp = FastMCP(name="CustomerSupportMCP")

# =============================================================================
# MCP Tools - These will appear in tools/list
# =============================================================================

@mcp.tool()
def get_customer(customer_id: int) -> str:
    """
    Get customer information by ID.
    
    Args:
        customer_id: The unique identifier of the customer
        
    Returns:
        JSON string with customer data
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.dumps({"success": True, "customer": dict(row)}, default=str)
    return json.dumps({"success": False, "error": f"Customer {customer_id} not found"})


@mcp.tool()
def list_customers(status: str = None, limit: int = 10) -> str:
    """
    List customers with optional status filter.
    
    Args:
        status: Filter by 'active' or 'disabled' (optional)
        limit: Maximum number to return (default 10)
        
    Returns:
        JSON string with list of customers
    """
    conn = get_db()
    cursor = conn.cursor()
    
    if status:
        cursor.execute("SELECT * FROM customers WHERE status = ? LIMIT ?", (status, limit))
    else:
        cursor.execute("SELECT * FROM customers LIMIT ?", (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return json.dumps({
        "success": True, 
        "customers": [dict(row) for row in rows],
        "count": len(rows)
    }, default=str)


@mcp.tool()
def update_customer(customer_id: int, email: str = None, phone: str = None, 
                   name: str = None, status: str = None) -> str:
    """
    Update customer information.
    
    Args:
        customer_id: The customer ID to update
        email: New email address (optional)
        phone: New phone number (optional)
        name: New name (optional)
        status: New status 'active' or 'disabled' (optional)
        
    Returns:
        JSON string with updated customer data
    """
    updates = {}
    if email: updates['email'] = email
    if phone: updates['phone'] = phone
    if name: updates['name'] = name
    if status: updates['status'] = status
    
    if not updates:
        return json.dumps({"success": False, "error": "No fields to update"})
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM customers WHERE id = ?", (customer_id,))
    if not cursor.fetchone():
        conn.close()
        return json.dumps({"success": False, "error": f"Customer {customer_id} not found"})
    
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values()) + [customer_id]
    cursor.execute(f"UPDATE customers SET {set_clause} WHERE id = ?", values)
    conn.commit()
    
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()
    
    return json.dumps({
        "success": True, 
        "customer": dict(row),
        "updated_fields": list(updates.keys())
    }, default=str)


@mcp.tool()
def create_ticket(customer_id: int, issue: str, priority: str = "medium") -> str:
    """
    Create a new support ticket.
    
    Args:
        customer_id: The customer ID
        issue: Description of the issue
        priority: 'low', 'medium', or 'high' (default: medium)
        
    Returns:
        JSON string with created ticket data
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name FROM customers WHERE id = ?", (customer_id,))
    customer = cursor.fetchone()
    if not customer:
        conn.close()
        return json.dumps({"success": False, "error": f"Customer {customer_id} not found"})
    
    cursor.execute(
        "INSERT INTO tickets (customer_id, issue, status, priority) VALUES (?, ?, 'open', ?)",
        (customer_id, issue, priority)
    )
    ticket_id = cursor.lastrowid
    conn.commit()
    
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    
    return json.dumps({
        "success": True,
        "ticket": dict(ticket),
        "customer_name": customer["name"]
    }, default=str)


@mcp.tool()
def get_customer_history(customer_id: int) -> str:
    """
    Get ticket history for a customer.
    
    Args:
        customer_id: The customer ID
        
    Returns:
        JSON string with customer info and ticket history
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    customer = cursor.fetchone()
    if not customer:
        conn.close()
        return json.dumps({"success": False, "error": "Customer not found"})
    
    cursor.execute("SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC", (customer_id,))
    tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    stats = {
        "total": len(tickets),
        "open": len([t for t in tickets if t["status"] == "open"]),
        "in_progress": len([t for t in tickets if t["status"] == "in_progress"]),
        "resolved": len([t for t in tickets if t["status"] == "resolved"])
    }
    
    return json.dumps({
        "success": True,
        "customer": dict(customer),
        "tickets": tickets,
        "statistics": stats
    }, default=str)


@mcp.tool()
def get_tickets_by_priority(priority: str, status: str = None) -> str:
    """
    Get tickets filtered by priority.
    
    Args:
        priority: 'low', 'medium', or 'high'
        status: Optional filter by 'open', 'in_progress', 'resolved'
        
    Returns:
        JSON string with filtered tickets
    """
    conn = get_db()
    cursor = conn.cursor()
    
    if status:
        cursor.execute("""
            SELECT t.*, c.name as customer_name
            FROM tickets t JOIN customers c ON t.customer_id = c.id
            WHERE t.priority = ? AND t.status = ?
        """, (priority, status))
    else:
        cursor.execute("""
            SELECT t.*, c.name as customer_name
            FROM tickets t JOIN customers c ON t.customer_id = c.id
            WHERE t.priority = ?
        """, (priority,))
    
    tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return json.dumps({"success": True, "tickets": tickets, "count": len(tickets)}, default=str)


@mcp.tool()
def get_active_customers_with_open_tickets() -> str:
    """
    Get all active customers who have open tickets.
    
    Returns:
        JSON string with active customers and their open tickets
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT c.id, c.name, c.email, c.status
        FROM customers c
        JOIN tickets t ON c.id = t.customer_id
        WHERE c.status = 'active' AND t.status = 'open'
    """)
    
    customers = cursor.fetchall()
    result = []
    
    for customer in customers:
        cursor.execute("""
            SELECT id, issue, priority FROM tickets 
            WHERE customer_id = ? AND status = 'open'
        """, (customer["id"],))
        
        open_tickets = [dict(t) for t in cursor.fetchall()]
        result.append({
            "customer": dict(customer),
            "open_tickets": open_tickets,
            "ticket_count": len(open_tickets)
        })
    
    conn.close()
    
    return json.dumps({
        "success": True,
        "customers": result,
        "total_customers": len(result)
    }, default=str)


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    setup_database()
    
    print("\n" + "="*60)
    print("🚀 MCP CUSTOMER SUPPORT SERVER")
    print("="*60)
    print("\nStarting MCP Server with SSE transport...")
    print("URL: http://localhost:8000/sse")
    print("\nTo test with MCP Inspector:")
    print("  npx @modelcontextprotocol/inspector")
    print("  Connect to: http://localhost:8000/sse")
    print("\nAvailable tools (tools/list):")
    print("  • get_customer(customer_id)")
    print("  • list_customers(status, limit)")
    print("  • update_customer(customer_id, email, phone, name, status)")
    print("  • create_ticket(customer_id, issue, priority)")
    print("  • get_customer_history(customer_id)")
    print("  • get_tickets_by_priority(priority, status)")
    print("  • get_active_customers_with_open_tickets()")
    print("="*60)
    print("\nPress Ctrl+C to stop\n")
    
    # Run with SSE transport - this is what MCP Inspector connects to
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
