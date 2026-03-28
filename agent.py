import json
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from database import log_audit
import tools

load_dotenv()

@tool
def check_global_news(keyword: str) -> str:
    """Check global news and events for supply chain disruptions by keyword."""
    res = tools.check_global_news(keyword)
    log_audit(
        action="check_global_news",
        decision=f"Checked news for '{keyword}'",
        guardrail_status="passed",
        details=res
    )
    return res

@tool
def check_inventory(product_id: str) -> str:
    """Check the inventory details for a given product ID (e.g., P001)."""
    res = tools.check_inventory(product_id)
    log_audit(
        action="check_inventory",
        decision="Inventory checked by agent",
        guardrail_status="passed",
        details=f"Target: {product_id} -> {res}"
    )
    return res

@tool
def check_supplier_status(supplier_id: str) -> str:
    """Check the status and location of a supplier by ID (e.g., S001)."""
    res = tools.check_supplier_status(supplier_id)
    log_audit(
        action="check_supplier_status",
        decision="Supplier checked by agent",
        guardrail_status="passed",
        details=f"Target: {supplier_id} -> {res}"
    )
    return res

@tool
def simulate_ripple_effect(product_id: str, delay_days: int) -> str:
    """Simulate the effect of a delay on a product's supply chain."""
    res = tools.simulate_ripple_effect(product_id, delay_days)
    log_audit(
        action="simulate_ripple_effect",
        decision=f"Simulated {delay_days} days delay for {product_id}",
        guardrail_status="passed",
        details=res
    )
    return res

@tool
def create_purchase_order(product_id: str, quantity: int, cost: float, supplier_id: str = "S001", force_override: bool = False) -> str:
    """
    Create a new purchase order.
    If the tool returns a BLOCKED status and the user explicitly authorizes an override, you must call this tool again and set force_override to True.
    """
    if force_override:
        # User explicitly bypassed guardrails via the UI
        import uuid
        from database import get_connection
        order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Orders (order_id, product_id, supplier_id, quantity, cost, status) VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, product_id, supplier_id, quantity, cost, "Approved (Override)")
        )
        conn.commit()
        conn.close()
        res = json.dumps({"order_id": order_id, "status": "OVERRIDDEN_AND_CREATED"})
        log_audit("create_purchase_order", "Order created (Override applied)", "overridden", res)
        return res

    res = tools.create_purchase_order(product_id, quantity, cost, supplier_id)
    data = json.loads(res)
    if data.get("status") == "BLOCKED":
        log_audit("create_purchase_order", "Order blocked by guardrails", "blocked", json.dumps(data))
    else:
        log_audit("create_purchase_order", "Order created safely", "passed", res)
    return res

@tool
def reroute_shipment(order_id: str, new_supplier: str, force_override: bool = False) -> str:
    """
    Reroute an existing shipment/order to a new supplier.
    If the tool returns a BLOCKED status and the user explicitly authorizes an override, you must call this tool again and set force_override to True.
    """
    if force_override:
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE Orders SET supplier_id = ? WHERE order_id = ?", (new_supplier, order_id))
        conn.commit()
        conn.close()
        res = json.dumps({"order_id": order_id, "new_supplier": new_supplier, "status": "Rerouted (Override)"})
        log_audit("reroute_shipment", "Shipment rerouted (Override applied)", "overridden", res)
        return res

    res = tools.reroute_shipment(order_id, new_supplier)
    data = json.loads(res)
    if data.get("status") == "BLOCKED":
        log_audit("reroute_shipment", "Reroute blocked by guardrails", "blocked", json.dumps(data))
    else:
        log_audit("reroute_shipment", "Shipment rerouted safely", "passed", res)
    return res


@tool
def query_database(sql_query: str) -> str:
    """
    Execute a READ-ONLY raw SQL query against the local SQLite database. 
    Use this to pull cross-table analytics, filter by risk level, category, price, or supplier. 
    Tables: Products, Inventory, Suppliers, Orders, Events, AuditLogs.
    """
    res = tools.query_database(sql_query)
    log_audit("query_database", f"Agent executed SQL query", "n/a", str(sql_query))
    return res

@tool
def query_external_api(url: str, params_json: str = "{}") -> str:
    """
    Query an external HTTP/REST API to fetch dynamic supply chain telemetry (like shipping status, tracking, or weather events).
    The url should be the full endpoint url provided by the user. params_json should be a JSON string of query parameters if needed.
    """
    res = tools.query_external_api(url, params_json)
    log_audit("query_external_api", f"Queried external API: {url}", "n/a", "External API response collected.")
    return res

agent_tools = [
    check_inventory,
    check_supplier_status,
    simulate_ripple_effect,
    create_purchase_order,
    reroute_shipment,
    query_external_api,
    query_database,
    check_global_news
]

# We prompt the system to act as Aegis
system_prompt = """
You are Aegis, an Autonomous Supply Chain Resilience Agent.
Your job is to:
1. Understand the user's query and context.
2. Call tools to fetch real data (inventory, suppliers). Do NOT hallucinate data. 
3. Use the `query_database` tool whenever the user asks analytical questions about the catalog (e.g., 'Find all products', 'Filter by price', 'Show risk levels'). Write raw SQLite SELECT statements.
4. Analyze results and simulate ripple effects if asked. You can use `check_global_news` specifically for checking major disruptions like port strikes.
5. If the user provides a third-party company URL/External API, you MUST use the `query_external_api` tool to fetch real-world data from it.
6. MUST Call the `create_purchase_order` and `reroute_shipment` tools whenever you are asked to place an order, make a purchase, or reroute a shipment! Never just reply "I will do it". It is CRITICAL that you physically click/call the tool.
7. If a tool returns a BLOCKED status, report this to the user immediately. Do not automatically bypass unless the user specifically authorizes it or uses the Override button.
8. Provide clear, concise responses.
"""

ACTIVE_LLM = os.getenv("ACTIVE_LLM", "gemini").lower()

if ACTIVE_LLM == "openai":
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
elif ACTIVE_LLM == "groq":
    llm = ChatGroq(model="llama3-70b-8192", temperature=0)
else:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

llm_with_tools = llm.bind_tools(agent_tools)

def chat_with_aegis(user_input: str, history: list | None = None) -> dict:
    log_audit("agent_start", "User query received", "passed", f"Query: {user_input}")
    try:
        messages = [SystemMessage(content=system_prompt)]
        
        if history:
            for msg in history:
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
        
        messages.append(HumanMessage(content=user_input))
        
        # Simple execution loop
        for _ in range(5):
            response = llm_with_tools.invoke(messages)
            messages.append(response)
            
            if not response.tool_calls:
                break
                
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # Execute mapped tool
                tool_func = next((t for t in agent_tools if t.name == tool_name), None)
                if tool_func:
                    res_str = tool_func.invoke(tool_args)
                    messages.append(ToolMessage(content=str(res_str), tool_call_id=tool_call["id"]))
                else:
                    messages.append(ToolMessage(content="Tool not found", tool_call_id=tool_call["id"]))
                    
        final_content = messages[-1].content
        if isinstance(final_content, list):
            final_output = "".join([str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in final_content])
        else:
            final_output = str(final_content)
            
        log_audit("agent_complete", "Successfully replied to user", "passed", "Execution succeeded.")
        return {"response": final_output, "actions": []}
    except Exception as e:
        error_msg = str(e)
        log_audit("agent_error", "Error executing agent", "failed", error_msg)
        return {"response": f"I encountered an error connecting to my core brain: {error_msg}", "actions": []}
