"""
Supplier Risk Scorer
Computes a 0-100 composite risk score per supplier based on:
  - Location risk (40 pts): restricted/sanctioned country or status
  - Order failure rate (40 pts): historical failed orders
  - Active disruption events (20 pts): matching Events table entries
"""
from datetime import datetime
from database import get_connection

HIGH_RISK_COUNTRIES = {"North Korea", "Syria", "Iran", "Cuba", "Russia"}


def _location_sub_score(location: str, status: str) -> float:
    """Returns 40 if supplier is in a high-risk country or has Restricted status, else 0."""
    if location in HIGH_RISK_COUNTRIES or status == "Restricted":
        return 40.0
    return 0.0


def _failure_sub_score(supplier_id: str) -> float:
    """
    Queries Orders for this supplier.
    failure_rate = failed_orders / total_orders
    Returns min(failure_rate * 40, 40). Returns 0 if no orders.
    Failed statuses: any status containing 'fail', 'cancel', 'block', 'reject'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM Orders WHERE supplier_id = ?", (supplier_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return 0.0

    failed_keywords = {"fail", "cancel", "block", "reject"}
    failed = sum(
        1 for r in rows
        if any(kw in r["status"].lower() for kw in failed_keywords)
    )
    failure_rate = failed / len(rows)
    return min(failure_rate * 40, 40.0)


def _disruption_sub_score(location: str) -> float:
    """Returns 20 if any active Events row matches the supplier's location, else 0."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM Events WHERE location = ?", (location,))
    row = cursor.fetchone()
    conn.close()
    return 20.0 if row["cnt"] > 0 else 0.0


def compute_risk_score(supplier_id: str) -> dict:
    """
    Computes composite risk score for a single supplier and persists to SupplierRiskScores.
    Returns a dict with all score fields.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Suppliers WHERE supplier_id = ?", (supplier_id,))
    supplier = cursor.fetchone()
    conn.close()

    if not supplier:
        return {"error": f"Supplier {supplier_id} not found"}

    loc_score = _location_sub_score(supplier["location"], supplier["status"])
    fail_score = _failure_sub_score(supplier_id)
    dis_score = _disruption_sub_score(supplier["location"])
    total = round(loc_score + fail_score + dis_score, 2)

    computed_at = datetime.now().isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO SupplierRiskScores
            (supplier_id, score, location_sub_score, failure_sub_score, disruption_sub_score, computed_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (supplier_id, total, loc_score, fail_score, dis_score, computed_at))
    conn.commit()
    conn.close()

    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier["name"],
        "location": supplier["location"],
        "score": total,
        "location_sub_score": loc_score,
        "failure_sub_score": fail_score,
        "disruption_sub_score": dis_score,
        "computed_at": computed_at,
    }


def compute_all_risk_scores() -> list[dict]:
    """Computes and persists risk scores for all suppliers. Returns list of score dicts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT supplier_id FROM Suppliers")
    supplier_ids = [row["supplier_id"] for row in cursor.fetchall()]
    conn.close()

    return [compute_risk_score(sid) for sid in supplier_ids]
