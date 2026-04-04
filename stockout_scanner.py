"""
Predictive Stockout Scanner
Proactively identifies products at risk of hitting reorder level within a given horizon.
"""
from database import get_connection


def _compute_daily_rate(reorder_level: int, lead_time_days: int) -> float:
    """Returns reorder_level / lead_time_days, guarded against division by zero."""
    if lead_time_days <= 0:
        return 0.0
    return reorder_level / lead_time_days


def scan_stockouts(horizon_days: int) -> list[dict]:
    """
    Scans all products and returns those at risk of stockout within horizon_days.

    A product is at risk when:
        stock - (daily_rate * horizon_days) <= reorder_level

    Returns a list of dicts with keys:
        product_id, product_name, current_stock, reorder_level,
        lead_time_days, estimated_days_until_stockout
    """
    if horizon_days < 1 or horizon_days > 365:
        raise ValueError(f"horizon_days must be between 1 and 365, got {horizon_days}")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.product_id, p.name, i.stock, i.reorder_level, i.lead_time_days
        FROM Products p
        JOIN Inventory i ON p.product_id = i.product_id
    """)
    rows = cursor.fetchall()
    conn.close()

    alerts = []
    for row in rows:
        daily_rate = _compute_daily_rate(row["reorder_level"], row["lead_time_days"])
        projected_stock = row["stock"] - (daily_rate * horizon_days)

        if projected_stock <= row["reorder_level"]:
            if daily_rate > 0:
                days_until = (row["stock"] - row["reorder_level"]) / daily_rate
            else:
                days_until = float("inf")

            alerts.append({
                "product_id": row["product_id"],
                "product_name": row["name"],
                "current_stock": row["stock"],
                "reorder_level": row["reorder_level"],
                "lead_time_days": row["lead_time_days"],
                "estimated_days_until_stockout": round(days_until, 1),
            })

    return alerts
