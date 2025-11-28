"""
MCP Server for Customer Support System
======================================
This is a proper MCP server implementation using FastMCP with SSE transport.
It exposes tools via the standard MCP protocol and can be tested with MCP Inspector.

Required Tools (from assignment):
- get_customer(customer_id)
- list_customers(status, limit)  
- update_customer(customer_id, data)
- create_ticket(customer_id, issue, priority)
- get_customer_history(customer_id)

To run:
    python mcp_server.py

To test with MCP Inspector:
    npx @anthropics/mcp-inspector
    Connect to: http://localhost:8000/sse
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server with SSE transport support
mcp = FastMCP(
    name="CustomerSupportMCP",
    version="1.0.0",
    description="MCP Server for Customer Support Database Operations"
)

# Database path
DB_PATH = "support.db"


def get_db_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
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
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'in_progress', 'resolved')),
            priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
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
            ("Fiona Green", "fiona.green@startup.io", "+1-555-0108", "disabled"),
            ("George Miller", "george.m@enterprise.com", "+1-555-0109", "active"),
            ("Hannah Lee", "hannah.lee@global.com", "+1-555-0110", "active"),
            ("Isaac Newton", "isaac.n@science.edu", "+1-555-0111", "active"),
            ("Julia Roberts", "julia.r@movies.com", "+1-555-0112", "active"),
            ("Kevin Chen", "kevin.chen@tech.io", "+1-555-0113", "disabled"),
            ("Laura Martinez", "laura.m@solutions.com", "+1-555-0114", "active"),
            ("Michael Scott", "michael.scott@paper.com", "+1-555-0115", "active"),
        ]
        cursor.executemany(
            "INSERT INTO customers (name, email, phone, status) VALUES (?, ?, ?, ?)",
            customers
        )
        
        # Insert sample tickets
        tickets = [
            (1, "Cannot login to account", "open", "high"),
            (4, "Database connection timeout errors", "in_progress", "high"),
            (7, "Payment processing failing", "open", "high"),
            (10, "Critical security vulnerability", "in_progress", "high"),
            (14, "Website completely down", "resolved", "high"),
            (1, "Password reset not working", "in_progress", "medium"),
            (2, "Profile image upload fails", "resolved", "medium"),
            (5, "Email notifications not received", "open", "medium"),
            (6, "Dashboard loading slowly", "in_progress", "medium"),
            (9, "Export to CSV broken", "open", "medium"),
            (11, "Mobile app crashes", "resolved", "medium"),
            (12, "Search returning wrong results", "in_progress", "medium"),
            (15, "API rate limiting too restrictive", "open", "medium"),
            (2, "Billing question about invoice", "resolved", "low"),
            (2, "Feature request: dark mode", "open", "low"),
            (3, "Documentation outdated", "open", "low"),
            (5, "Typo in welcome email", "resolved", "low"),
            (6, "Request language support", "open", "low"),
            (9, "Font size too small", "resolved", "low"),
            (11, "Feature request: PDF export", "open", "low"),
        ]
        cursor.executemany(
            "INSERT INTO tickets (customer_id, issue, status, priority) VALUES (?, ?, ?, ?)",
            tickets
        )
        
        conn.commit()
        print("Database initialized with sample data")
    
    conn.close()


# ==================== MCP Tools ====================

@mcp.tool()
def get_customer(customer_id: int) -> dict:
    """
    Get customer information by ID.
    
    Args:
        customer_id: The unique identifier of the customer
        
    Returns:
        Customer data including id, name, email, phone, status, and timestamps
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, email, phone, status, created_at, updated_at
        FROM customers WHERE id = ?
    """, (customer_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "success": True,
            "customer": dict(row)
        }
    return {
        "success": False,
        "error": f"Customer with ID {customer_id} not found"
    }


@mcp.tool()
def list_customers(status: str = None, limit: int = 10) -> dict:
    """
    List customers with optional status filter and limit.
    
    Args:
        status: Filter by status ('active' or 'disabled'), None for all
        limit: Maximum number of customers to return (default 10)
        
    Returns:
        List of customers matching the criteria
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if status:
        if status not in ['active', 'disabled']:
            return {
                "success": False,
                "error": f"Invalid status: {status}. Must be 'active' or 'disabled'"
            }
        cursor.execute("""
            SELECT id, name, email, phone, status, created_at, updated_at
            FROM customers WHERE status = ? ORDER BY id LIMIT ?
        """, (status, limit))
    else:
        cursor.execute("""
            SELECT id, name, email, phone, status, created_at, updated_at
            FROM customers ORDER BY id LIMIT ?
        """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return {
        "success": True,
        "customers": [dict(row) for row in rows],
        "count": len(rows)
    }


@mcp.tool()
def update_customer(customer_id: int, name: str = None, email: str = None, 
                    phone: str = None, status: str = None) -> dict:
    """
    Update customer information.
    
    Args:
        customer_id: The unique identifier of the customer
        name: New name (optional)
        email: New email (optional)
        phone: New phone (optional)
        status: New status - 'active' or 'disabled' (optional)
        
    Returns:
        Updated customer data
    """
    updates = {}
    if name: updates['name'] = name
    if email: updates['email'] = email
    if phone: updates['phone'] = phone
    if status: 
        if status not in ['active', 'disabled']:
            return {"success": False, "error": "Invalid status"}
        updates['status'] = status
    
    if not updates:
        return {"success": False, "error": "No fields to update"}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if customer exists
    cursor.execute("SELECT id FROM customers WHERE id = ?", (customer_id,))
    if not cursor.fetchone():
        conn.close()
        return {"success": False, "error": f"Customer {customer_id} not found"}
    
    # Build and execute update query
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values()) + [customer_id]
    
    cursor.execute(f"UPDATE customers SET {set_clause} WHERE id = ?", values)
    conn.commit()
    
    # Return updated customer
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()
    
    return {
        "success": True,
        "customer": dict(row),
        "updated_fields": list(updates.keys())
    }


@mcp.tool()
def create_ticket(customer_id: int, issue: str, priority: str = "medium") -> dict:
    """
    Create a new support ticket.
    
    Args:
        customer_id: The customer ID for the ticket
        issue: Description of the issue
        priority: Priority level ('low', 'medium', 'high')
        
    Returns:
        Created ticket data
    """
    if priority not in ['low', 'medium', 'high']:
        return {"success": False, "error": f"Invalid priority: {priority}"}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check customer exists
    cursor.execute("SELECT id, name FROM customers WHERE id = ?", (customer_id,))
    customer = cursor.fetchone()
    if not customer:
        conn.close()
        return {"success": False, "error": f"Customer {customer_id} not found"}
    
    # Create ticket
    cursor.execute("""
        INSERT INTO tickets (customer_id, issue, status, priority)
        VALUES (?, ?, 'open', ?)
    """, (customer_id, issue, priority))
    
    ticket_id = cursor.lastrowid
    conn.commit()
    
    # Fetch created ticket
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    
    return {
        "success": True,
        "ticket": dict(ticket),
        "customer_name": customer["name"]
    }


@mcp.tool()
def get_customer_history(customer_id: int) -> dict:
    """
    Get ticket history for a customer.
    
    Args:
        customer_id: The unique identifier of the customer
        
    Returns:
        Customer info and their ticket history with statistics
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get customer
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    customer = cursor.fetchone()
    if not customer:
        conn.close()
        return {"success": False, "error": f"Customer {customer_id} not found"}
    
    # Get tickets
    cursor.execute("""
        SELECT id, issue, status, priority, created_at
        FROM tickets WHERE customer_id = ? ORDER BY created_at DESC
    """, (customer_id,))
    
    tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Calculate statistics
    stats = {
        "total_tickets": len(tickets),
        "open_tickets": len([t for t in tickets if t["status"] == "open"]),
        "in_progress_tickets": len([t for t in tickets if t["status"] == "in_progress"]),
        "resolved_tickets": len([t for t in tickets if t["status"] == "resolved"]),
        "high_priority": len([t for t in tickets if t["priority"] == "high"])
    }
    
    return {
        "success": True,
        "customer": dict(customer),
        "tickets": tickets,
        "statistics": stats
    }


@mcp.tool()
def get_tickets_by_priority(priority: str, status: str = None) -> dict:
    """
    Get tickets filtered by priority and optionally by status.
    
    Args:
        priority: Priority level ('low', 'medium', 'high')
        status: Optional status filter ('open', 'in_progress', 'resolved')
        
    Returns:
        List of tickets matching the criteria
    """
    if priority not in ['low', 'medium', 'high']:
        return {"success": False, "error": f"Invalid priority: {priority}"}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if status:
        cursor.execute("""
            SELECT t.*, c.name as customer_name
            FROM tickets t JOIN customers c ON t.customer_id = c.id
            WHERE t.priority = ? AND t.status = ?
            ORDER BY t.created_at DESC
        """, (priority, status))
    else:
        cursor.execute("""
            SELECT t.*, c.name as customer_name
            FROM tickets t JOIN customers c ON t.customer_id = c.id
            WHERE t.priority = ?
            ORDER BY t.created_at DESC
        """, (priority,))
    
    tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        "success": True,
        "tickets": tickets,
        "count": len(tickets)
    }


@mcp.tool()
def get_active_customers_with_open_tickets() -> dict:
    """
    Get all active customers who have open tickets.
    
    Returns:
        List of active customers with their open tickets
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT c.* FROM customers c
        JOIN tickets t ON c.id = t.customer_id
        WHERE c.status = 'active' AND t.status = 'open'
        ORDER BY c.name
    """)
    
    customers = cursor.fetchall()
    result = []
    
    for customer in customers:
        cursor.execute("""
            SELECT id, issue, priority, created_at
            FROM tickets WHERE customer_id = ? AND status = 'open'
            ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
        """, (customer["id"],))
        
        open_tickets = [dict(t) for t in cursor.fetchall()]
        result.append({
            "customer": dict(customer),
            "open_tickets": open_tickets
        })
    
    conn.close()
    
    return {
        "success": True,
        "customers": result,
        "total_customers": len(result),
        "total_open_tickets": sum(len(c["open_tickets"]) for c in result)
    }


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    # Initialize database
    setup_database()
    
    print("="*60)
    print("MCP Customer Support Server")
    print("="*60)
    print("\nStarting MCP Server with SSE transport...")
    print("Server URL: http://localhost:8000/sse")
    print("\nTo test with MCP Inspector:")
    print("  npx @modelcontextprotocol/inspector")
    print("  Connect to: http://localhost:8000/sse")
    print("\nAvailable tools:")
    print("  - get_customer(customer_id)")
    print("  - list_customers(status, limit)")
    print("  - update_customer(customer_id, ...)")
    print("  - create_ticket(customer_id, issue, priority)")
    print("  - get_customer_history(customer_id)")
    print("  - get_tickets_by_priority(priority, status)")
    print("  - get_active_customers_with_open_tickets()")
    print("="*60)
    
    # Run with SSE transport
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
