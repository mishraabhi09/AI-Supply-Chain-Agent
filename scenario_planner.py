"""
What-If Scenario Planner
Evaluates the financial and operational impact of a supplier going offline.
Returns affected products, total financial exposure, and alternative supplier recommendations.
"""
from risk_scorer import HIGH_RISK_COUNTRIES
from database import get_connection


def _get_affected_products(supplier_id: str) -> list[dict]:
    """Returns products linked to the supplier via the Orders table, with exposure calculated."""
    conn = get_connection()
    cursor = conn.cursor()
    # Find distinct products ordered from this supplier, join with product/inventory data
    cursor.execute("""
        SELECT DISTINCT p.product_id, p.name, p.unit_cost, i.stock
        FROM Orders o
        JOIN Products p ON o.product_id = p.product_id
        JOIN Inventory i ON p.product_id = i.product_id
        WHERE o.supplier_id = ?
    """, (supplier_id,))
    rows = cursor.fetchall()
    conn.close()

    products = []
    for row in rows:
        exposure = round((row["unit_cost"] or 0.0) * (row["stock"] or 0), 2)
        products.append({
            "product_id": row["product_id"],
            "name": row["name"],
            "unit_cost": row["unit_cost"],
            "stock": row["stock"],
            "exposure": exposure,
        })
    return products


def _get_alternative_suppliers(exclude_id: str) -> list[dict]:
    """Returns up to 3 Active suppliers not in restricted locations and not the excluded one."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT supplier_id, name, location, status
        FROM Suppliers
        WHERE status = 'Active'
          AND supplier_id != ?
          AND location NOT IN ('North Korea', 'Syria', 'Iran', 'Cuba', 'Russia')
        LIMIT 3
    """, (exclude_id,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {"supplier_id": r["supplier_id"], "name": r["name"], "location": r["location"]}
        for r in rows
    ]


def run_scenario(supplier_id: str, offline_days: int) -> dict:
    """
    Runs a what-if scenario: what happens if supplier_id goes offline for offline_days?

    Returns:
        scenario_summary, affected_products, total_financial_exposure, currency, recommended_alternatives
    """
    if offline_days < 1 or offline_days > 365:
        raise ValueError(f"offline_days must be between 1 and 365, got {offline_days}")

    # Validate supplier exists
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Suppliers WHERE supplier_id = ?", (supplier_id,))
    supplier = cursor.fetchone()
    conn.close()

    if not supplier:
        raise ValueError(f"Supplier '{supplier_id}' not found in the database.")

    affected = _get_affected_products(supplier_id)
    total_exposure = round(sum(p["exposure"] for p in affected), 2)
    alternatives = _get_alternative_suppliers(supplier_id)

    summary = (
        f"If supplier {supplier['name']} ({supplier_id}) goes offline for {offline_days} days, "
        f"{len(affected)} product(s) are affected with a total financial exposure of "
        f"${total_exposure:,.2f} USD. "
        f"{len(alternatives)} alternative supplier(s) are available."
    )

    return {
        "scenario_summary": summary,
        "affected_products": affected,
        "total_financial_exposure": total_exposure,
        "currency": "USD",
        "recommended_alternatives": alternatives,
        "offline_days": offline_days,
        "supplier_id": supplier_id,
        "supplier_name": supplier["name"],
    }
