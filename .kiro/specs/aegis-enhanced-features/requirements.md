# Requirements Document

## Introduction

This document defines the requirements for enhancing the Aegis Autonomous Supply Chain Resilience Agent with seven major feature areas: predictive stockout alerts, supplier risk scoring, multi-agent orchestration, real news integration, what-if scenario planning, conversational memory persistence, and a set of quick-win engineering improvements. The goal is to produce an interview-ready, production-quality system built on the existing FastAPI + Streamlit + LangChain + SQLite stack.

---

## Glossary

- **Aegis**: The overall autonomous supply chain resilience system.
- **Coordinator**: The top-level orchestration agent that delegates tasks to sub-agents.
- **Procurement_Agent**: A specialized sub-agent responsible for inventory analysis, purchase order creation, and stockout detection.
- **Risk_Intelligence_Agent**: A specialized sub-agent responsible for supplier risk scoring, news monitoring, and disruption event analysis.
- **Stockout_Scanner**: The component that evaluates inventory levels against lead times to predict future stockouts.
- **Risk_Scorer**: The component that computes a 0–100 risk score per supplier from location, order failure history, and disruption events.
- **News_Fetcher**: The component that retrieves live disruption news from an external API (NewsAPI, GDELT, or RSS).
- **Scenario_Planner**: The component that evaluates user-defined hypothetical disruption scenarios and computes financial exposure.
- **Session_Store**: The SQLite-backed persistence layer for chat history across sessions.
- **Guardrails**: The rule-based safety layer that blocks or flags high-risk agent actions.
- **AuditLogs**: The SQLite table recording every agent action, decision, and guardrail outcome.
- **FastAPI_Backend**: The FastAPI application serving the `/api/chat` and related endpoints.
- **Streamlit_Frontend**: The Streamlit application providing the user interface.

---

## Requirements

### Requirement 1: Predictive Stockout Alerts

**User Story:** As a supply chain manager, I want the system to proactively identify products that will reach their reorder level within their lead time window, so that I can act before a stockout occurs.

#### Acceptance Criteria

1. WHEN the Stockout_Scanner is invoked with a horizon parameter N (in days), THE Stockout_Scanner SHALL query all products where `stock - (daily_consumption_rate * N) <= reorder_level`.
2. THE Stockout_Scanner SHALL derive `daily_consumption_rate` from the existing `lead_time_days` and `reorder_level` columns when no explicit consumption data is available, using the formula `reorder_level / lead_time_days`.
3. WHEN at least one at-risk product is found, THE Stockout_Scanner SHALL return a structured list containing `product_id`, `product_name`, `current_stock`, `reorder_level`, `lead_time_days`, and `estimated_days_until_stockout` for each at-risk product.
4. WHEN no at-risk products are found, THE Stockout_Scanner SHALL return a response indicating no stockout risk within the given horizon.
5. THE Procurement_Agent SHALL expose `scan_stockout_alerts` as a callable tool that accepts a `horizon_days` integer parameter.
6. WHEN the Streamlit_Frontend loads the "Predictive Alerts" panel, THE Streamlit_Frontend SHALL call the `/api/stockout-alerts` endpoint and display the results in a color-coded table (red for critical, amber for warning).
7. IF the `horizon_days` parameter is less than 1 or greater than 365, THEN THE FastAPI_Backend SHALL return HTTP 422 with a descriptive validation error.

---

### Requirement 2: Supplier Risk Scoring Dashboard

**User Story:** As a procurement analyst, I want a visual risk score (0–100) for each supplier, so that I can prioritize supplier diversification and contingency planning.

#### Acceptance Criteria

1. THE Risk_Scorer SHALL compute a composite risk score for each supplier on a 0–100 scale using three weighted sub-scores: location risk (40%), historical order failure rate (40%), and active disruption events (20%).
2. WHEN a supplier's `location` matches a country in the restricted or high-risk country list, THE Risk_Scorer SHALL assign the maximum location sub-score of 40.
3. WHEN a supplier has no recorded order failures, THE Risk_Scorer SHALL assign an order failure sub-score of 0.
4. WHEN a supplier has one or more active Events records matching their location, THE Risk_Scorer SHALL assign the maximum disruption sub-score of 20.
5. THE Risk_Scorer SHALL persist computed scores to a `SupplierRiskScores` table containing `supplier_id`, `score`, `location_sub_score`, `failure_sub_score`, `disruption_sub_score`, and `computed_at`.
6. WHEN the Streamlit_Frontend renders the "Supplier Risk Dashboard" tab, THE Streamlit_Frontend SHALL display a horizontal bar chart of all supplier risk scores using Streamlit's native `st.bar_chart` or Altair.
7. WHEN a supplier's composite score exceeds 70, THE Streamlit_Frontend SHALL highlight that supplier's row in red in the accompanying data table.
8. THE Risk_Intelligence_Agent SHALL expose `get_supplier_risk_scores` as a callable tool that returns the latest scores for all suppliers.

---

### Requirement 3: Multi-Agent Orchestration

**User Story:** As a developer, I want the single monolithic agent split into a Coordinator, a Procurement Agent, and a Risk Intelligence Agent, so that each agent has a focused responsibility and the system is easier to extend.

#### Acceptance Criteria

1. THE Coordinator SHALL receive all user queries and route them to the Procurement_Agent, the Risk_Intelligence_Agent, or both, based on query intent classification.
2. WHEN a query contains intent related to inventory, purchase orders, or stockouts, THE Coordinator SHALL delegate to the Procurement_Agent.
3. WHEN a query contains intent related to supplier risk, news events, or disruptions, THE Coordinator SHALL delegate to the Risk_Intelligence_Agent.
4. WHEN a query requires both procurement and risk context, THE Coordinator SHALL invoke both sub-agents sequentially and merge their responses before replying to the user.
5. THE Procurement_Agent SHALL have access to the tools: `check_inventory`, `simulate_ripple_effect`, `create_purchase_order`, `scan_stockout_alerts`, and `query_database`.
6. THE Risk_Intelligence_Agent SHALL have access to the tools: `check_supplier_status`, `check_global_news`, `get_supplier_risk_scores`, `query_database`, and `run_scenario`.
7. THE Coordinator SHALL pass the full conversation history to each sub-agent it invokes so that sub-agents have context.
8. IF a sub-agent returns an error or times out, THEN THE Coordinator SHALL return a graceful error message to the user without crashing.
9. THE FastAPI_Backend SHALL expose the Coordinator as the sole entry point via the existing `/api/chat` endpoint, maintaining backward compatibility.

---

### Requirement 4: Real News Integration

**User Story:** As a risk analyst, I want the agent to fetch live global disruption news instead of returning hardcoded mock data, so that the risk assessments reflect real-world conditions.

#### Acceptance Criteria

1. WHEN `check_global_news` is called with a keyword, THE News_Fetcher SHALL query a live external news source (NewsAPI, GDELT Project API, or a public RSS feed) using that keyword.
2. THE News_Fetcher SHALL read the API key and source selection from environment variables (`NEWS_API_KEY`, `NEWS_SOURCE`) so that no credentials are hardcoded.
3. WHEN the external news API returns results, THE News_Fetcher SHALL parse and return a structured JSON list of up to 5 articles, each containing `title`, `source`, `published_at`, `url`, and `relevance_keyword`.
4. IF the external news API is unreachable or returns a non-200 status, THEN THE News_Fetcher SHALL fall back to the existing hardcoded mock data and include a `"fallback": true` flag in the response.
5. IF the `NEWS_API_KEY` environment variable is not set, THEN THE News_Fetcher SHALL use the fallback mock data and log a warning to `error.log`.
6. THE News_Fetcher SHALL cache the last successful API response in memory for 15 minutes to avoid redundant API calls for the same keyword within a session.

---

### Requirement 5: What-If Scenario Planner

**User Story:** As a supply chain strategist, I want to define hypothetical disruption scenarios (e.g., "Supplier S001 goes offline for 30 days") and receive a full impact analysis with financial exposure and alternative supplier recommendations, so that I can prepare contingency plans.

#### Acceptance Criteria

1. WHEN a user submits a scenario via the `/api/scenario` endpoint specifying a `supplier_id` and `offline_days`, THE Scenario_Planner SHALL identify all products sourced from that supplier.
2. THE Scenario_Planner SHALL calculate the financial exposure for each affected product as `unit_cost * stock` and sum these to produce a total portfolio exposure value.
3. THE Scenario_Planner SHALL query the Suppliers table for alternative suppliers that are `Active`, not in a restricted location, and not the disrupted supplier, and include up to 3 alternatives in the response.
4. WHEN the Scenario_Planner completes analysis, THE Scenario_Planner SHALL return a structured JSON response containing `scenario_summary`, `affected_products` (list), `total_financial_exposure`, `currency` (USD), and `recommended_alternatives` (list).
5. THE Risk_Intelligence_Agent SHALL expose `run_scenario` as a callable tool accepting `supplier_id` (string) and `offline_days` (integer).
6. WHEN the Streamlit_Frontend renders the "What-If Planner" tab, THE Streamlit_Frontend SHALL provide input fields for `supplier_id` and `offline_days`, a "Run Scenario" button, and a results panel displaying the structured output.
7. IF the specified `supplier_id` does not exist in the database, THEN THE Scenario_Planner SHALL return an error response with a descriptive message.
8. IF `offline_days` is less than 1 or greater than 365, THEN THE FastAPI_Backend SHALL return HTTP 422 with a descriptive validation error.

---

### Requirement 6: Conversational Memory and Session Persistence

**User Story:** As a user, I want my chat history to be saved to the database so that I can resume conversations across browser sessions without losing context.

#### Acceptance Criteria

1. THE Session_Store SHALL persist each chat message to a `ChatSessions` SQLite table containing `session_id`, `role` (`user` or `assistant`), `content`, and `timestamp`.
2. WHEN the Streamlit_Frontend initializes, THE Streamlit_Frontend SHALL generate or retrieve a `session_id` stored in `st.session_state` and use it for all subsequent messages in that browser session.
3. WHEN a user sends a message, THE FastAPI_Backend SHALL write the user message and the agent response to the `ChatSessions` table under the active `session_id` before returning the response.
4. WHEN the Streamlit_Frontend loads, THE Streamlit_Frontend SHALL call the `/api/sessions/{session_id}/history` endpoint and pre-populate `st.session_state.messages` with the returned history.
5. THE FastAPI_Backend SHALL expose a `GET /api/sessions/{session_id}/history` endpoint that returns all messages for the given session ordered by timestamp ascending.
6. THE FastAPI_Backend SHALL expose a `DELETE /api/sessions/{session_id}` endpoint that clears all messages for the given session.
7. WHEN the user clicks "Clear Session" in the Streamlit_Frontend, THE Streamlit_Frontend SHALL call the DELETE endpoint and reset `st.session_state.messages` to an empty list.
8. IF the `ChatSessions` table does not exist, THEN THE Session_Store SHALL create it automatically during database initialization.

---

### Requirement 7: Quick-Win Engineering Improvements

**User Story:** As a developer, I want a `/metrics` endpoint, input validation, rate limiting, and unit tests for guardrails, so that the system is production-hardened and demonstrably reliable.

#### Acceptance Criteria

1. THE FastAPI_Backend SHALL expose a `GET /metrics` endpoint that returns a JSON object containing `total_orders`, `blocked_orders`, `total_audit_logs`, `active_suppliers`, and `uptime_seconds`.
2. WHEN the `/api/chat` endpoint receives a request where `query` is an empty string or exceeds 2000 characters, THE FastAPI_Backend SHALL return HTTP 422 with a descriptive validation error.
3. THE FastAPI_Backend SHALL enforce a rate limit of 30 requests per minute per client IP on the `/api/chat` endpoint using a token-bucket or sliding-window algorithm.
4. IF a client exceeds the rate limit, THEN THE FastAPI_Backend SHALL return HTTP 429 with a `Retry-After` header indicating when the client may retry.
5. THE Guardrails test suite SHALL include a unit test verifying that `validate_order_cost` returns a BLOCKED result for any cost value strictly greater than 10000.
6. THE Guardrails test suite SHALL include a unit test verifying that `validate_order_cost` returns `None` for any cost value of exactly 10000 or less.
7. THE Guardrails test suite SHALL include a unit test verifying that `validate_supplier_location` returns a BLOCKED result when the supplier's location is in the restricted list.
8. THE Guardrails test suite SHALL include a unit test verifying that `check_guardrails_for_reroute` always returns a BLOCKED result regardless of supplier location.
9. THE Guardrails test suite SHALL include a unit test verifying that `validate_supplier_location` returns `None` for a supplier in a non-restricted, active location.
