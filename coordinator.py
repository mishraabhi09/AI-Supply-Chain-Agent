"""
Coordinator Agent
Top-level orchestrator that classifies user intent and routes to the appropriate sub-agent(s).
Maintains backward compatibility with the existing /api/chat endpoint.
"""
from database import log_audit
from procurement_agent import ProcurementAgent
from risk_agent import RiskIntelligenceAgent

# Intent classification keyword sets
PROCUREMENT_KEYWORDS = {
    "inventory", "stock", "order", "purchase", "stockout", "reorder",
    "lead time", "product", "sku", "quantity", "units", "warehouse",
    "replenish", "shortage", "supply", "demand",
}

RISK_KEYWORDS = {
    "supplier", "risk", "news", "disruption", "event", "scenario",
    "reroute", "score", "sanction", "restrict", "geopolit", "strike",
    "delay", "port", "weather", "crisis", "alternative", "backup",
}


class Coordinator:
    def __init__(self):
        self._procurement_agent = None
        self._risk_agent = None

    @property
    def procurement_agent(self) -> ProcurementAgent:
        if self._procurement_agent is None:
            self._procurement_agent = ProcurementAgent()
        return self._procurement_agent

    @property
    def risk_agent(self) -> RiskIntelligenceAgent:
        if self._risk_agent is None:
            self._risk_agent = RiskIntelligenceAgent()
        return self._risk_agent

    def classify_intent(self, query: str) -> list[str]:
        """
        Classifies query intent using keyword matching.
        Returns list containing 'procurement', 'risk', or both.
        Defaults to both if no clear signal.
        """
        query_lower = query.lower()
        has_procurement = any(kw in query_lower for kw in PROCUREMENT_KEYWORDS)
        has_risk = any(kw in query_lower for kw in RISK_KEYWORDS)

        if has_procurement and has_risk:
            return ["procurement", "risk"]
        elif has_procurement:
            return ["procurement"]
        elif has_risk:
            return ["risk"]
        else:
            # Default: try procurement first (most common queries)
            return ["procurement", "risk"]

    def run(self, query: str, history: list[dict] | None = None) -> dict:
        """
        Routes query to sub-agents based on intent, merges responses if both are needed.
        Returns {"response": str, "actions": list}.
        """
        log_audit("coordinator_start", f"Routing query: {query[:100]}", "passed", f"Query length: {len(query)}")
        intents = self.classify_intent(query)
        responses = []

        if "procurement" in intents:
            try:
                result = self.procurement_agent.run(query, history)
                responses.append(result.get("response", ""))
                log_audit("coordinator_procurement", "Procurement agent responded", "passed", "")
            except Exception as e:
                log_audit("coordinator_procurement_error", "Procurement agent failed", "failed", str(e))
                responses.append(f"⚠️ Procurement analysis encountered an error: {e}")

        if "risk" in intents:
            try:
                result = self.risk_agent.run(query, history)
                responses.append(result.get("response", ""))
                log_audit("coordinator_risk", "Risk agent responded", "passed", "")
            except Exception as e:
                log_audit("coordinator_risk_error", "Risk agent failed", "failed", str(e))
                responses.append(f"⚠️ Risk intelligence analysis encountered an error: {e}")

        if not responses:
            return {"response": "I was unable to process your request. Please try again.", "actions": []}

        # If both agents responded, merge with a separator
        if len(responses) == 2 and intents == ["procurement", "risk"]:
            merged = responses[0]
            if responses[1] and responses[1] != responses[0]:
                merged += f"\n\n---\n\n{responses[1]}"
            final_response = merged
        else:
            final_response = responses[0]

        log_audit("coordinator_complete", "Response delivered to user", "passed", f"Intents: {intents}")
        return {"response": final_response, "actions": []}


# Module-level singleton for use in main.py
_coordinator_instance = None

def get_coordinator() -> Coordinator:
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = Coordinator()
    return _coordinator_instance


def chat_with_aegis(user_input: str, history: list | None = None) -> dict:
    """Backward-compatible entry point. Replaces agent.py's chat_with_aegis."""
    return get_coordinator().run(user_input, history)
