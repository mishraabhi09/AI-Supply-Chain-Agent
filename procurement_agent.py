"""
Procurement Agent
Specialized sub-agent focused on inventory management, purchase orders, and stockout detection.
"""
import os
import json
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from database import log_audit
import tools as t

load_dotenv()

PROCUREMENT_SYSTEM_PROMPT = """
You are the Procurement Agent within the Aegis Supply Chain system.
Your specialization is inventory management, purchase orders, and stockout prevention.

Your responsibilities:
1. Check inventory levels and identify at-risk products using scan_stockout_alerts.
2. Simulate ripple effects of supply delays.
3. Create purchase orders when needed (always call the tool — never just say you will).
4. Use query_database for analytical questions about products, inventory, and orders.
5. If a tool returns BLOCKED, report it clearly to the user.
6. Be concise and data-driven in your responses.
"""

ACTIVE_LLM = os.getenv("ACTIVE_LLM", "gemini").lower()

def _get_llm():
    if ACTIVE_LLM == "openai":
        return ChatOpenAI(model="gpt-4o", temperature=0)
    elif ACTIVE_LLM == "groq":
        return ChatGroq(model="llama3-70b-8192", temperature=0)
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)


@tool
def check_inventory(product_id: str) -> str:
    """Check the inventory details for a given product ID (e.g., P001)."""
    return t.check_inventory(product_id)

@tool
def simulate_ripple_effect(product_id: str, delay_days: int) -> str:
    """Simulate the downstream impact of a supply delay on a product."""
    return t.simulate_ripple_effect(product_id, delay_days)

@tool
def create_purchase_order(product_id: str, quantity: int, cost: float, supplier_id: str = "S001", force_override: bool = False) -> str:
    """Create a new purchase order. Set force_override=True only when admin has explicitly authorized."""
    return t.create_purchase_order(product_id, quantity, cost, supplier_id)

@tool
def scan_stockout_alerts(horizon_days: int = 30) -> str:
    """Scan all products for stockout risk within the given horizon (days). Default is 30 days."""
    return t.scan_stockout_alerts(horizon_days)

@tool
def query_database(sql_query: str) -> str:
    """Execute a READ-ONLY SQL query. Tables: Products, Inventory, Suppliers, Orders, Events, AuditLogs."""
    return t.query_database(sql_query)


PROCUREMENT_TOOLS = [check_inventory, simulate_ripple_effect, create_purchase_order, scan_stockout_alerts, query_database]


class ProcurementAgent:
    def __init__(self):
        llm = _get_llm()
        self.llm_with_tools = llm.bind_tools(PROCUREMENT_TOOLS)

    def run(self, query: str, history: list[dict] | None = None) -> dict:
        messages = [SystemMessage(content=PROCUREMENT_SYSTEM_PROMPT)]

        if history:
            for msg in history:
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=query))

        try:
            for _ in range(5):
                response = self.llm_with_tools.invoke(messages)
                messages.append(response)

                if not response.tool_calls:
                    break

                for tc in response.tool_calls:
                    tool_func = next((t for t in PROCUREMENT_TOOLS if t.name == tc["name"]), None)
                    if tool_func:
                        result = tool_func.invoke(tc["args"])
                        messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                    else:
                        messages.append(ToolMessage(content="Tool not found", tool_call_id=tc["id"]))

            final = messages[-1].content
            if isinstance(final, list):
                final = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in final)
            return {"response": str(final), "agent": "procurement"}

        except Exception as e:
            log_audit("procurement_agent_error", "Error in procurement agent", "failed", str(e))
            return {"response": f"Procurement agent error: {e}", "agent": "procurement"}
