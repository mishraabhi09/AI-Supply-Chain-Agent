"""
Risk Intelligence Agent
Specialized sub-agent focused on supplier risk, live news, disruption events, and scenario planning.
"""
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from database import log_audit
import tools as t

load_dotenv()

RISK_SYSTEM_PROMPT = """
You are the Risk Intelligence Agent within the Aegis Supply Chain system.
Your specialization is supplier risk assessment, global disruption monitoring, and scenario planning.

Your responsibilities:
1. Check supplier status and compute risk scores using get_supplier_risk_scores.
2. Fetch live global news for supply chain disruptions using check_global_news.
3. Run what-if scenarios to evaluate financial exposure using run_scenario.
4. Use query_database for analytical questions about suppliers, events, and risk data.
5. Provide clear, actionable risk assessments with specific recommendations.
6. Always cite data sources and scores in your responses.
"""

ACTIVE_LLM = os.getenv("ACTIVE_LLM", "gemini").lower()

def _get_llm():
    if ACTIVE_LLM == "openai":
        return ChatOpenAI(model="gpt-4o", temperature=0)
    elif ACTIVE_LLM == "groq":
        return ChatGroq(model="llama3-70b-8192", temperature=0)
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)


@tool
def check_supplier_status(supplier_id: str) -> str:
    """Check the status and location of a supplier by ID (e.g., S001)."""
    return t.check_supplier_status(supplier_id)

@tool
def check_global_news(keyword: str) -> str:
    """Fetch live global news for supply chain disruptions by keyword (e.g., 'port strike', 'Taiwan')."""
    return t.check_global_news(keyword)

@tool
def get_supplier_risk_scores() -> str:
    """Compute and return risk scores (0-100) for all suppliers based on location, failures, and disruptions."""
    return t.get_supplier_risk_scores()

@tool
def run_scenario(supplier_id: str, offline_days: int) -> str:
    """Run a what-if scenario: what if supplier_id goes offline for offline_days? Returns financial exposure and alternatives."""
    return t.run_scenario(supplier_id, offline_days)

@tool
def reroute_shipment(order_id: str, new_supplier: str, force_override: bool = False) -> str:
    """Reroute an existing shipment to a new supplier. Requires override for high-risk actions."""
    return t.reroute_shipment(order_id, new_supplier)

@tool
def query_database(sql_query: str) -> str:
    """Execute a READ-ONLY SQL query. Tables: Products, Inventory, Suppliers, Orders, Events, AuditLogs."""
    return t.query_database(sql_query)


RISK_TOOLS = [check_supplier_status, check_global_news, get_supplier_risk_scores, run_scenario, reroute_shipment, query_database]


class RiskIntelligenceAgent:
    def __init__(self):
        llm = _get_llm()
        self.llm_with_tools = llm.bind_tools(RISK_TOOLS)

    def run(self, query: str, history: list[dict] | None = None) -> dict:
        messages = [SystemMessage(content=RISK_SYSTEM_PROMPT)]

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
                    tool_func = next((t for t in RISK_TOOLS if t.name == tc["name"]), None)
                    if tool_func:
                        result = tool_func.invoke(tc["args"])
                        messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                    else:
                        messages.append(ToolMessage(content="Tool not found", tool_call_id=tc["id"]))

            final = messages[-1].content
            if isinstance(final, list):
                final = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in final)
            return {"response": str(final), "agent": "risk"}

        except Exception as e:
            log_audit("risk_agent_error", "Error in risk intelligence agent", "failed", str(e))
            return {"response": f"Risk intelligence agent error: {e}", "agent": "risk"}
