import time
from collections import deque
from typing import Optional

from fastapi import FastAPI, Query, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field

from coordinator import chat_with_aegis
import stockout_scanner
import scenario_planner
import session_store
from database import get_connection, init_db

try:
    init_db()
except Exception:
    pass

_start_time = time.time()

app = FastAPI(
    title="Aegis Autonomous Supply Chain Resilience Agent",
    description="API for managing supply chain resilience via AI agent.",
    version="2.0.0",
)


# ── Rate Limiting Middleware ───────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter: 30 requests/60s per IP on /api/chat."""
    _windows: dict = {}
    LIMIT = 30
    WINDOW_SECONDS = 60

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/api/chat":
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            window = self._windows.setdefault(client_ip, deque())
            while window and now - window[0] > self.WINDOW_SECONDS:
                window.popleft()
            if len(window) >= self.LIMIT:
                retry_after = int(self.WINDOW_SECONDS - (now - window[0])) + 1
                return Response(
                    content='{"detail":"Rate limit exceeded. Try again later."}',
                    status_code=429,
                    headers={"Retry-After": str(retry_after), "Content-Type": "application/json"},
                )
            window.append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)


# ── Pydantic Models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    history: list = []
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    actions: list = []

class StockoutAlert(BaseModel):
    product_id: str
    product_name: str
    current_stock: int
    reorder_level: int
    lead_time_days: int
    estimated_days_until_stockout: float

class ScenarioRequest(BaseModel):
    supplier_id: str
    offline_days: int = Field(ge=1, le=365)

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: str

class MetricsResponse(BaseModel):
    total_orders: int
    blocked_orders: int
    total_audit_logs: int
    active_suppliers: int
    uptime_seconds: float


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "Welcome to Aegis API v2.0. The system is running."}

@app.get("/health")
def health_check():
    return {"status": "healthy", "uptime_seconds": round(time.time() - _start_time, 1)}

@app.post("/api/chat", response_model=ChatResponse)
def chat_with_agent(request: ChatRequest):
    result = chat_with_aegis(request.query, request.history)
    response_text = result.get("response", "Error processing request.")
    if request.session_id:
        try:
            session_store.save_message(request.session_id, "user", request.query)
            session_store.save_message(request.session_id, "assistant", response_text)
        except Exception:
            pass
    return ChatResponse(response=response_text, actions=result.get("actions", []))

@app.get("/api/stockout-alerts", response_model=list[StockoutAlert])
def get_stockout_alerts(horizon_days: int = Query(default=30, ge=1, le=365)):
    return stockout_scanner.scan_stockouts(horizon_days)

@app.post("/api/scenario")
def run_scenario_endpoint(request: ScenarioRequest):
    try:
        return scenario_planner.run_scenario(request.supplier_id, request.offline_days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/sessions/{session_id}/history", response_model=list[ChatMessage])
def get_session_history(session_id: str):
    return session_store.get_history(session_id)

@app.delete("/api/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    session_store.delete_session(session_id)
    return {"status": "cleared", "session_id": session_id}

@app.get("/metrics", response_model=MetricsResponse)
def get_metrics():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM Orders")
    total_orders = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) as cnt FROM AuditLogs WHERE guardrail_status = 'blocked'")
    blocked_orders = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) as cnt FROM AuditLogs")
    total_audit_logs = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) as cnt FROM Suppliers WHERE status = 'Active'")
    active_suppliers = cursor.fetchone()["cnt"]
    conn.close()
    return MetricsResponse(
        total_orders=total_orders,
        blocked_orders=blocked_orders,
        total_audit_logs=total_audit_logs,
        active_suppliers=active_suppliers,
        uptime_seconds=round(time.time() - _start_time, 1),
    )
