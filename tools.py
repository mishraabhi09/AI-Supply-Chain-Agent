import json
import uuid
import requests
from datetime import datetime
from database import get_connection
from guardrails import check_guardrails_for_order, check_guardrails_for_reroute
import sqlite3

def query_database(sql_query: str) -> str:
    """Execute a READ-ONLY SQL query against the supply_chain.db database."""
    # Guard against destructive queries
    if any(keyword in sql_query.upper() for keyword in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]):
        return json.dumps({"status": "BLOCKED", "reason": "Only SELECT read-only queries are permitted for this tool."})
    
    try:
        conn = sqlite3.connect("supply_chain.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to list of dicts then json
        result = [dict(row) for row in rows]
        # Return truncated JSON to avoid blowing up context window
        return json.dumps(result)[:3000] # Safe limit for token context
    except Exception as e:
        return json.dumps({"error": f"Error executing query: {e}"})

def query_external_api(url: str, params_json: str = "{}") -> str:
    """
    Query an external REST API for supply chain telemetry.
    """
    try:
        params = json.loads(params_json)
        response = requests.get(url, params=params, timeout=10)
        # Attempt to parse json, fallback to text
        try:
            return json.dumps(response.json())
        except ValueError:
            return response.text
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch data from API: {str(e)}"})

def check_global_news(keyword: str) -> str:
    """Check global news and events for supply chain disruptions by keyword."""
    keyword_lower = keyword.lower()
    if "rotterdam" in keyword_lower or "port" in keyword_lower or "strike" in keyword_lower:
        return json.dumps({
            "event": "Port Strike",
            "location": "Rotterdam",
            "severity": "Critical",
            "estimated_delay_days": 14,
            "description": "Major port strike in Rotterdam causing severe shipping delays."
        })
    return json.dumps({"status": "No major disruptions found for this keyword."})

def check_inventory(product_id: str) -> str:
    """Check the inventory details for a given product ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Inventory WHERE product_id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.dumps(dict(row))
    return json.dumps({"error": f"Product {product_id} not found."})

def check_supplier_status(supplier_id: str) -> str:
    """Check the status and location of a supplier."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Suppliers WHERE supplier_id = ?", (supplier_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.dumps(dict(row))
    return json.dumps({"error": f"Supplier {supplier_id} not found."})

def simulate_ripple_effect(product_id: str, delay_days: int) -> str:
    """Simulate the effect of a delay on a product's supply chain. Returns risk assessment JSON."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Inventory WHERE product_id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return json.dumps({"error": f"Product {product_id} not found."})
        
    stock = row['stock']
    lead_time = row['lead_time_days']
    reorder_level = row['reorder_level']
    
    # Basic logic for ripple effect impact
    impact = "Low"
    if delay_days >= lead_time:
        impact = "High - Stockout in 2 days. Production halt in 5 days."
    elif stock < reorder_level:
        impact = "Medium - Reorder recommended"
    
    return json.dumps({
        "product_id": product_id,
        "simulated_delay_days": delay_days,
        "current_stock": stock,
        "lead_time_days": lead_time,
        "impact_assessment": impact
    })

def create_purchase_order(product_id: str, quantity: int, cost: float, supplier_id: str = "S001") -> str:
    """
    Create a new purchase order. 
    Note: Guardrails should validate cost and supplier before execution in the agent layer, 
    but the tool executes the action and returns structured output.
    """
    # 1. Check Guardrails
    guardrail_result = check_guardrails_for_order(supplier_id, cost)
    if guardrail_result:
        return guardrail_result

    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Orders (order_id, product_id, supplier_id, quantity, cost, status) VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, product_id, supplier_id, quantity, cost, "Pending")
        )
        conn.commit()
        result = {
            "order_id": order_id, 
            "product_id": product_id, 
            "supplier_id": supplier_id, 
            "quantity": quantity,
            "cost": cost,
            "status": "Created"
        }
    except Exception as e:
        result = {"error": str(e)}
    finally:
        conn.close()
        
    return json.dumps(result)

def reroute_shipment(order_id: str, new_supplier: str) -> str:
    """Reroute an existing shipment/order to a new supplier."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Orders WHERE order_id = ?", (order_id,))
    order = cursor.fetchone()
    
    if not order:
        conn.close()
        return json.dumps({"error": f"Order {order_id} not found."})
        
    # 1. Check Guardrails
    guardrail_result = check_guardrails_for_reroute(new_supplier)
    if guardrail_result:
        conn.close()
        return guardrail_result

    old_supplier = order['supplier_id']
    cursor.execute("UPDATE Orders SET supplier_id = ? WHERE order_id = ?", (new_supplier, order_id))
    conn.commit()
    conn.close()
    
    return json.dumps({
        "order_id": order_id,
        "previous_supplier": old_supplier,
        "new_supplier": new_supplier,
        "status": "Rerouted successfully"
    })
    
