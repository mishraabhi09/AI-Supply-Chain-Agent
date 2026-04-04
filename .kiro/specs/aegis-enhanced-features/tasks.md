# Implementation Plan: Aegis Enhanced Features

## Overview

Incrementally extend the existing FastAPI + Streamlit + LangChain + SQLite stack with seven feature areas. New modules are introduced as separate files; existing files (`main.py`, `app.py`, `database.py`, `tools.py`, `agent.py`) are extended minimally. All changes are additive and backward-compatible with the existing `/api/chat` endpoint.

Implementation language: **Python**

---

## Tasks

- [x] 1. Extend database schema and update requirements.txt
  - [x] 1.1 Add `SupplierRiskScores` and `ChatSessions` tables to `database.py`
    - Add `CREATE TABLE IF NOT EXISTS SupplierRiskScores` and `CREATE TABLE IF NOT EXISTS ChatSessions` DDL (with indexes) inside `init_db()` executescript
    - Extend `migrate_db()` to handle any future column additions for these tables
    - Verify `init_db()` is idempotent (safe to call on an existing DB)
    - _Requirements: 2.5, 6.1, 6.8_

  - [ ]* 1.2 Write unit test for database migration idempotency
    - Call `init_db()` twice on a fresh temp DB and assert no exception is raised and both new tables exist
    - _Requirements: 6.8_

  - [x] 1.3 Update `requirements.txt` with new dependencies
    - Add: `pytest`, `hypothesis`, `pytest-asyncio`, `httpx`, `newsapi-python`, `slowapi`, `requests`
    - _Requirements: 7.5 (test infra)_

- [x] 2. Implement Predictive Stockout Scanner (`stockout_scanner.py`)
  - [x] 2.1 Create `stockout_scanner.py` with `scan_stockouts(horizon_days)` and `_compute_daily_rate`
    - Query `Products JOIN Inventory`; filter `stock - (daily_rate * horizon_days) <= reorder_level`
    - Derive `daily_rate = reorder_level / lead_time_days`; guard division by zero (return 0.0)
    - Compute `estimated_days_until_stockout = (stock - reorder_level) / daily_rate`
    - Raise `ValueError` if `horizon_days < 1` or `horizon_days > 365`
    - Return list of dicts with keys: `product_id`, `product_name`, `current_stock`, `reorder_level`, `lead_time_days`, `estimated_days_until_stockout`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 2.2 Write property test for stockout filter correctness (Property 1)
    - **Property 1: Stockout filter correctness**
    - **Validates: Requirements 1.1, 1.2, 1.3**
    - File: `tests/test_stockout_scanner.py`
    - Use `@given(st.integers(min_value=1, max_value=365))` with synthetic inventory rows
    - Assert every returned product satisfies the inequality; assert `estimated_days_until_stockout` formula

- [x] 3. Implement Supplier Risk Scorer (`risk_scorer.py`)
  - [x] 3.1 Create `risk_scorer.py` with `compute_risk_score`, `compute_all_risk_scores`, and sub-score helpers
    - Define `HIGH_RISK_COUNTRIES = {"North Korea", "Syria", "Iran", "Cuba", "Russia"}`
    - `_location_sub_score(location, status)`: return 40 if location in set or status == 'Restricted', else 0
    - `_failure_sub_score(supplier_id)`: query Orders; `failure_rate = failed_orders / total_orders`; return `min(failure_rate * 40, 40)`; return 0 if no orders
    - `_disruption_sub_score(location)`: return 20 if any Events row matches location, else 0
    - `compute_risk_score(supplier_id)`: sum sub-scores, persist to `SupplierRiskScores`, return dataclass/dict
    - `compute_all_risk_scores()`: iterate all suppliers, call `compute_risk_score` for each
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 3.2 Write property test for risk score composite invariant (Property 2)
    - **Property 2: Risk score composite invariant**
    - **Validates: Requirements 2.1**
    - File: `tests/test_risk_scorer.py`
    - Assert `score == location_sub + failure_sub + disruption_sub` and `0 <= score <= 100`

  - [ ]* 3.3 Write property test for restricted location sub-score (Property 3)
    - **Property 3: Restricted location yields maximum location sub-score**
    - **Validates: Requirements 2.2**
    - Use `st.sampled_from(HIGH_RISK_COUNTRIES)` and assert `_location_sub_score` returns exactly 40

  - [ ]* 3.4 Write property test for active disruption sub-score (Property 4)
    - **Property 4: Active disruption yields maximum disruption sub-score**
    - **Validates: Requirements 2.4**
    - Insert a matching Events row in temp DB; assert `_disruption_sub_score` returns exactly 20

  - [ ]* 3.5 Write property test for risk score persistence round-trip (Property 5)
    - **Property 5: Risk score persistence round-trip**
    - **Validates: Requirements 2.5**
    - After `compute_risk_score(supplier_id)`, query `SupplierRiskScores` and assert all fields match

- [x] 4. Implement News Fetcher (`news_fetcher.py`)
  - [x] 4.1 Create `news_fetcher.py` with `fetch_news`, `_call_newsapi`, `_call_gdelt`, and `_fallback_mock`
    - Module-level `_cache: dict = {}` with `CACHE_TTL_SECONDS = 900`
    - `fetch_news(keyword)`: check cache TTL → call NewsAPI if `NEWS_API_KEY` set → parse up to 5 articles into `{title, source, published_at, url, relevance_keyword}` dicts → on failure or missing key, call `_fallback_mock` and add `"fallback": True`
    - Read `NEWS_API_KEY` and `NEWS_SOURCE` from `os.environ`; log `WARNING` to `error.log` via `logging` if key missing
    - `_fallback_mock(keyword)`: return existing hardcoded mock data from `tools.check_global_news` with `"fallback": True`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 4.2 Write property test for news article output structure (Property 8)
    - **Property 8: News article output structure**
    - **Validates: Requirements 4.3**
    - File: `tests/test_news_fetcher.py`
    - Mock `requests.get`; assert result list has ≤ 5 items and each item has all required keys

  - [ ]* 4.3 Write property test for news cache idempotence within TTL (Property 9)
    - **Property 9: News cache idempotence within TTL**
    - **Validates: Requirements 4.6**
    - Mock `requests.get`; call `fetch_news` twice within TTL; assert HTTP mock called exactly once and both calls return identical data

- [x] 5. Implement Scenario Planner (`scenario_planner.py`)
  - [x] 5.1 Create `scenario_planner.py` with `run_scenario`, `_get_affected_products`, and `_get_alternative_suppliers`
    - `run_scenario(supplier_id, offline_days)`: validate supplier exists (raise `ValueError` if not); raise `ValueError` if `offline_days < 1` or `> 365`
    - `_get_affected_products(supplier_id)`: query products linked via Orders table; compute `exposure = unit_cost * stock` per product
    - Sum exposures for `total_financial_exposure`
    - `_get_alternative_suppliers(exclude_id)`: query up to 3 Active suppliers not in restricted locations and not equal to `exclude_id`
    - Return dict: `{scenario_summary, affected_products, total_financial_exposure, currency: "USD", recommended_alternatives}`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.7_

  - [ ]* 5.2 Write property test for scenario financial exposure calculation (Property 10)
    - **Property 10: Scenario financial exposure calculation**
    - **Validates: Requirements 5.1, 5.2, 5.4**
    - File: `tests/test_scenario_planner.py`
    - Assert `total_financial_exposure == sum(p["unit_cost"] * p["stock"] for p in affected_products)` and all required keys present

  - [ ]* 5.3 Write property test for scenario alternatives validity (Property 11)
    - **Property 11: Scenario alternatives validity**
    - **Validates: Requirements 5.3**
    - Assert every alternative has `status == 'Active'`, is not in restricted country list, is not the disrupted supplier, and list length ≤ 3

- [x] 6. Implement Session Store (`session_store.py`)
  - [x] 6.1 Create `session_store.py` with `save_message`, `get_history`, and `delete_session`
    - `save_message(session_id, role, content)`: insert row into `ChatSessions` with ISO 8601 timestamp
    - `get_history(session_id)`: return all messages ordered by `timestamp ASC` as list of `{role, content, timestamp}` dicts
    - `delete_session(session_id)`: delete all `ChatSessions` rows for the given `session_id`
    - _Requirements: 6.1, 6.3, 6.5, 6.6_

  - [ ]* 6.2 Write property test for session persistence round-trip (Property 12)
    - **Property 12: Session persistence round-trip**
    - **Validates: Requirements 6.1, 6.3**
    - File: `tests/test_session_store.py`
    - Use `st.text()` for session_id, role, content; after `save_message`, assert `get_history` contains matching entry

  - [ ]* 6.3 Write property test for session history ordering (Property 13)
    - **Property 13: Session history ordering**
    - **Validates: Requirements 6.5**
    - Insert multiple messages with distinct timestamps; assert `get_history` returns them in ascending order

  - [ ]* 6.4 Write property test for session delete clears all messages (Property 14)
    - **Property 14: Session delete clears all messages**
    - **Validates: Requirements 6.6**
    - After `delete_session`, assert `get_history` returns empty list

- [ ] 7. Checkpoint — core modules complete
  - Ensure `stockout_scanner.py`, `risk_scorer.py`, `news_fetcher.py`, `scenario_planner.py`, and `session_store.py` are importable without errors.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Multi-Agent Orchestration (`procurement_agent.py`, `risk_agent.py`, `coordinator.py`)
  - [x] 8.1 Create `procurement_agent.py` wrapping a LangChain ReAct loop
    - Bind tools: `check_inventory`, `simulate_ripple_effect`, `create_purchase_order`, `scan_stockout_alerts` (new tool wrapping `stockout_scanner.scan_stockouts`), `query_database`
    - Expose `ProcurementAgent.run(query, history) -> dict` returning `{response, actions}`
    - Reuse LLM selection logic from `agent.py` (`ACTIVE_LLM` env var)
    - _Requirements: 3.2, 3.5_

  - [x] 8.2 Create `risk_agent.py` wrapping a LangChain ReAct loop
    - Bind tools: `check_supplier_status`, `check_global_news` (updated to call `news_fetcher.fetch_news`), `get_supplier_risk_scores` (new tool calling `risk_scorer.compute_all_risk_scores`), `query_database`, `run_scenario` (new tool calling `scenario_planner.run_scenario`)
    - Expose `RiskIntelligenceAgent.run(query, history) -> dict`
    - _Requirements: 3.3, 3.6_

  - [x] 8.3 Create `coordinator.py` with `Coordinator.classify_intent` and `Coordinator.run`
    - `classify_intent(query)`: keyword-set fast path → return `['procurement']`, `['risk']`, or both; LLM fallback if ambiguous
    - Procurement keywords: `inventory`, `stock`, `order`, `purchase`, `stockout`, `reorder`, `lead time`, `product`
    - Risk keywords: `supplier`, `risk`, `news`, `disruption`, `event`, `scenario`, `reroute`, `score`
    - `run(query, history)`: route to `ProcurementAgent`, `RiskIntelligenceAgent`, or both sequentially; pass full history to each sub-agent; merge responses if both invoked; wrap each sub-agent call in try/except and log to `AuditLogs` on error; return graceful error message on failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7, 3.8, 3.9_

  - [ ]* 8.4 Write property test for coordinator routing correctness (Property 6)
    - **Property 6: Coordinator routing correctness**
    - **Validates: Requirements 3.1, 3.2, 3.3**
    - File: `tests/test_coordinator.py`
    - Use `st.sampled_from(procurement_keywords)` and `st.sampled_from(risk_keywords)`; assert `classify_intent` returns correct intent list

  - [ ]* 8.5 Write property test for coordinator history propagation (Property 7)
    - **Property 7: Coordinator history propagation**
    - **Validates: Requirements 3.7**
    - Mock sub-agents; use `st.lists(st.fixed_dictionaries({...}))` for history; assert each sub-agent receives the same history list

- [x] 9. Extend `tools.py` with new agent-callable tool wrappers
  - Add `scan_stockout_alerts(horizon_days)` function calling `stockout_scanner.scan_stockouts`
  - Add `get_supplier_risk_scores()` function calling `risk_scorer.compute_all_risk_scores`
  - Add `run_scenario(supplier_id, offline_days)` function calling `scenario_planner.run_scenario`
  - Update `check_global_news(keyword)` to delegate to `news_fetcher.fetch_news` instead of the hardcoded mock
  - _Requirements: 1.5, 2.8, 4.1, 5.5_

- [x] 10. Extend `main.py` with new endpoints, rate limiting, input validation, and metrics
  - [x] 10.1 Add Pydantic models: `StockoutAlert`, `ScenarioRequest`, `ChatMessage`, `MetricsResponse`; update `ChatRequest` with `Field(min_length=1, max_length=2000)` and optional `session_id`
    - _Requirements: 1.7, 5.8, 7.2_

  - [x] 10.2 Implement `RateLimitMiddleware` as `BaseHTTPMiddleware`
    - Sliding-window counter: `dict[str, deque]` keyed by client IP
    - Limit: 30 requests / 60 seconds on `/api/chat` only
    - Return HTTP 429 with `Retry-After` header on breach
    - Register middleware with `app.add_middleware(RateLimitMiddleware)`
    - _Requirements: 7.3, 7.4_

  - [x] 10.3 Add `GET /api/stockout-alerts` endpoint
    - Parameter: `horizon_days: int = Query(default=30, ge=1, le=365)`
    - Call `stockout_scanner.scan_stockouts(horizon_days)`; return list of `StockoutAlert`
    - _Requirements: 1.6, 1.7_

  - [x] 10.4 Add `POST /api/scenario` endpoint
    - Body: `ScenarioRequest(supplier_id, offline_days: int = Field(ge=1, le=365))`
    - Call `scenario_planner.run_scenario`; catch `ValueError` and return HTTP 404 with descriptive message
    - _Requirements: 5.1, 5.7, 5.8_

  - [x] 10.5 Add `GET /api/sessions/{session_id}/history` and `DELETE /api/sessions/{session_id}` endpoints
    - History endpoint: call `session_store.get_history`; return list of `ChatMessage` ordered by timestamp ASC
    - Delete endpoint: call `session_store.delete_session`; return `{"status": "cleared"}`
    - _Requirements: 6.4, 6.5, 6.6_

  - [x] 10.6 Add `GET /metrics` endpoint
    - Query DB for `total_orders`, `blocked_orders` (guardrail_status == 'blocked' in AuditLogs), `total_audit_logs`, `active_suppliers`
    - Compute `uptime_seconds` from a module-level `_start_time = time.time()` set at import
    - Return `MetricsResponse`
    - _Requirements: 7.1_

  - [x] 10.7 Update `POST /api/chat` to use `Coordinator` and persist messages to `ChatSessions`
    - Replace `chat_with_aegis` call with `Coordinator().run(query, history)`
    - After getting response, call `session_store.save_message` for both user message and assistant response (if `session_id` provided)
    - _Requirements: 3.9, 6.3_

  - [ ]* 10.8 Write property test for chat input validation (Property 15)
    - **Property 15: Chat input validation rejects invalid lengths**
    - **Validates: Requirements 7.2**
    - File: `tests/test_main.py`
    - Use FastAPI `TestClient`; assert HTTP 422 for empty string and strings > 2000 chars

  - [ ]* 10.9 Write property test for rate limiting enforcement (Property 16)
    - **Property 16: Rate limiting enforcement with Retry-After**
    - **Validates: Requirements 7.3, 7.4**
    - Send 31 requests from same IP within window; assert 31st returns HTTP 429 with `Retry-After` header

- [ ] 11. Checkpoint — backend complete
  - Ensure all new endpoints are reachable and return expected shapes.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Write guardrails unit tests (`tests/test_guardrails.py`)
  - [x] 12.1 Create `tests/test_guardrails.py` with unit tests for `validate_order_cost` and `validate_supplier_location`
    - Test: `validate_order_cost(10001)` returns dict with `status == 'BLOCKED'` (Req 7.5)
    - Test: `validate_order_cost(10000)` returns `None` (Req 7.6)
    - Test: `validate_order_cost(9999.99)` returns `None` (Req 7.6)
    - Test: `validate_supplier_location` with a restricted-country supplier returns `status == 'BLOCKED'` (Req 7.7)
    - Test: `check_guardrails_for_reroute` with any supplier returns non-None with `status == 'BLOCKED'` (Req 7.8)
    - Test: `validate_supplier_location` with an Active, non-restricted supplier returns `None` (Req 7.9)
    - _Requirements: 7.5, 7.6, 7.7, 7.8, 7.9_

  - [ ]* 12.2 Write property test for guardrail cost threshold (Property 17)
    - **Property 17: Guardrail cost threshold**
    - **Validates: Requirements 7.5, 7.6**
    - File: `tests/test_guardrails.py`
    - `@given(st.floats(min_value=10000.01, max_value=1e9, allow_nan=False))` → assert BLOCKED
    - `@given(st.floats(min_value=0, max_value=10000, allow_nan=False))` → assert None

  - [ ]* 12.3 Write property test for guardrail location blocking (Property 18)
    - **Property 18: Guardrail location blocking**
    - **Validates: Requirements 7.7, 7.9**
    - `st.sampled_from(restricted_locations)` → assert BLOCKED; `st.text()` for non-restricted Active supplier → assert None

  - [ ]* 12.4 Write property test for reroute always blocked (Property 19)
    - **Property 19: Reroute always blocked**
    - **Validates: Requirements 7.8**
    - `@given(st.text())` for supplier_id → assert `check_guardrails_for_reroute` returns non-None with `status == 'BLOCKED'`

- [x] 13. Extend `app.py` with new Streamlit tabs
  - [x] 13.1 Add session ID initialization and history pre-population to `app.py`
    - On load: generate or retrieve `session_id` in `st.session_state` (use `uuid.uuid4()` if not present)
    - Call `GET /api/sessions/{session_id}/history` and pre-populate `st.session_state.messages`
    - Pass `session_id` in all `/api/chat` payloads
    - Add "Clear Session" button that calls `DELETE /api/sessions/{session_id}` and resets `st.session_state.messages`
    - _Requirements: 6.2, 6.4, 6.7_

  - [x] 13.2 Add "Predictive Alerts" tab to `app.py`
    - Add tab using `st.tabs`; inside tab: `horizon_days` number input (1–365, default 30)
    - Call `GET /api/stockout-alerts?horizon_days=N` on button click
    - Display results in a color-coded `st.dataframe` (red for `estimated_days_until_stockout < lead_time_days`, amber for others)
    - Show "No stockout risk" message when list is empty
    - _Requirements: 1.6_

  - [x] 13.3 Add "Supplier Risk Dashboard" tab to `app.py`
    - Call `GET /api/chat` with a `get_supplier_risk_scores` intent query to retrieve scores
    - Display horizontal bar chart using `st.bar_chart` or Altair
    - Display accompanying data table; highlight rows with `score > 70` in red
    - _Requirements: 2.6, 2.7_

  - [x] 13.4 Add "What-If Planner" tab to `app.py`
    - Input fields: `supplier_id` (text), `offline_days` (number, 1–365)
    - "Run Scenario" button calls `POST /api/scenario`
    - Results panel displays `scenario_summary`, `affected_products` table, `total_financial_exposure`, and `recommended_alternatives` list
    - _Requirements: 5.6_

- [x] 14. Final checkpoint — full integration
  - Ensure all tests pass, ask the user if questions arise.
  - Verify `/api/chat` backward compatibility (existing payloads without `session_id` still work).
  - Verify all 7 new UI tabs/panels render without errors.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use `pytest-hypothesis` with `@settings(max_examples=100)`
- Each property test must include a comment: `# Feature: aegis-enhanced-features, Property N: <text>`
- `agent.py` is kept unchanged as a reference; `coordinator.py` becomes the new entry point
- All DB changes use `CREATE TABLE IF NOT EXISTS` — safe to run on existing databases
- `conftest.py` in `tests/` should provide a `test_db` fixture using `tmp_path` for isolation
