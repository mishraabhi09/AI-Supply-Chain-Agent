import json
from database import get_connection

def validate_order_cost(cost: float) -> dict | None:
    if cost > 10000:
        return {
            "status": "BLOCKED",
            "reason": f"Order cost ${cost:,.2f} exceeds the $10,000 maximum threshold.",
            "requires_human": True
        }
    return None


def validate_supplier_location(supplier_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Suppliers WHERE supplier_id = ?", (supplier_id,))
    supplier = cursor.fetchone()
    conn.close()
    
    if not supplier:
        return {
            "status": "BLOCKED",
            "reason": f"Supplier {supplier_id} not found.",
            "requires_human": False
        }
        
    restricted_locations = ["North Korea", "Syria", "Iran", "Cuba", "Russia"]
    if supplier['location'] in restricted_locations or supplier['status'] == 'Restricted':
        return {
            "status": "BLOCKED",
            "reason": f"Supplier {supplier_id} is in a restricted location ({supplier['location']}) or has Restricted status.",
            "requires_human": True
        }
    return None

def check_guardrails_for_order(supplier_id: str, cost: float) -> str | None:
    """Run guardrails for purchasing. Returns JSON string if blocked, else None."""
    cost_check = validate_order_cost(cost)
    if cost_check:
        return json.dumps(cost_check)
        
    location_check = validate_supplier_location(supplier_id)
    if location_check:
        return json.dumps(location_check)
        
    return None

def check_guardrails_for_reroute(new_supplier_id: str) -> str | None:
    """Run guardrails for rerouting a shipment."""
    location_check = validate_supplier_location(new_supplier_id)
    if location_check:
        return json.dumps(location_check)
        
    # High-risk action: Rerouting always requires human approval by default
    return json.dumps({
        "status": "BLOCKED",
        "reason": f"Rerouting shipments to {new_supplier_id} is a high-risk action and requires explicit override.",
        "requires_human": True
    })
