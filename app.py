import uuid
import streamlit as st
import requests
import pandas as pd
import sqlite3
from export_utils import export_csv, export_pdf, export_docx
from database import migrate_db

try:
    migrate_db()
except Exception:
    pass

st.set_page_config(page_title="Aegis Supply Chain Agent", layout="wide")

BACKEND = "http://127.0.0.1:8000"

st.markdown("""
<style>
div[data-testid="stDownloadButton"] button {
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
    border: none !important;
}
div[data-testid="column"]:nth-child(1) div[data-testid="stDownloadButton"] button {
    background-color: #1a7f4b !important; color: #ffffff !important;
}
div[data-testid="column"]:nth-child(2) div[data-testid="stDownloadButton"] button {
    background-color: #c0392b !important; color: #ffffff !important;
}
div[data-testid="column"]:nth-child(3) div[data-testid="stDownloadButton"] button {
    background-color: #1a56a0 !important; color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Aegis: Autonomous Supply Chain Resilience Agent")
st.markdown("Monitor disruptions, analyze risk, and execute guarded supply chain decisions.")

# ── Session ID Management ─────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    # Try to load persisted history from backend
    try:
        res = requests.get(f"{BACKEND}/api/sessions/{st.session_state.session_id}/history", timeout=3)
        if res.status_code == 200:
            history = res.json()
            st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in history]
        else:
            st.session_state.messages = []
    except Exception:
        st.session_state.messages = []

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("📁 Real Data Integration")
with st.sidebar.expander("Upload CSV Data (.csv)", expanded=False):
    st.info("Upload your company's real CSV data to dynamically overwrite the current database tables.")
    upload_table = st.selectbox("Select Table:", ["Products", "Inventory", "Suppliers", "Orders", "Events"])
    uploaded_file = st.file_uploader(f"Upload ({upload_table})", type=["csv", "xlsx"])
    if uploaded_file is not None:
        if st.button(f"Overwrite {upload_table} Table", type="secondary"):
            with st.spinner("Writing to database..."):
                try:
                    if uploaded_file.name.endswith(".csv"):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)
                    conn = sqlite3.connect("supply_chain.db")
                    df.to_sql(upload_table, conn, if_exists="replace", index=False)
                    conn.close()
                    st.success(f"✅ Successfully updated {upload_table} with {len(df)} rows!")
                except Exception as e:
                    st.error(f"Error uploading data: {e}")

st.sidebar.divider()

with st.sidebar.expander("🔍 Preview Database Data", expanded=False):
    preview_table = st.selectbox("Select Table to Preview:", ["Products", "Inventory", "Suppliers", "Orders", "Events"])
    if st.button(f"Load {preview_table}"):
        try:
            conn = sqlite3.connect("supply_chain.db")
            preview_df = pd.read_sql_query(f"SELECT * FROM {preview_table} LIMIT 100", conn)
            conn.close()
            st.dataframe(preview_df, use_container_width=True)
            st.markdown("##### 📥 Export Data")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.download_button("CSV", data=export_csv(preview_df), file_name=f"{preview_table}_export.csv", mime="text/csv", use_container_width=True)
            with c2:
                st.download_button("PDF", data=export_pdf(preview_df, f"{preview_table} Data"), file_name=f"{preview_table}_export.pdf", mime="application/pdf", use_container_width=True)
            with c3:
                st.download_button("Word", data=export_docx(preview_df, f"{preview_table} Data"), file_name=f"{preview_table}_export.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        except Exception as e:
            st.error(f"Could not load {preview_table}: {e}")

st.sidebar.divider()

# Audit Logs
st.sidebar.title("📑 Live Audit Logs")

def load_logs():
    try:
        conn = sqlite3.connect("supply_chain.db")
        df = pd.read_sql_query("SELECT timestamp, action, decision, guardrail_status, details FROM AuditLogs ORDER BY log_id DESC LIMIT 1000", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

logs_df_full = load_logs()
logs_df = logs_df_full.head(30)
if not logs_df.empty:
    st.sidebar.dataframe(
        logs_df.style.applymap(
            lambda x: 'background-color: #ffcccc; color: #111111; font-weight: 600' if x == 'blocked'
                 else ('background-color: #ccffcc; color: #111111; font-weight: 600' if x == 'passed'
                 else ('background-color: #fff3cd; color: #111111; font-weight: 600' if x == 'overridden' else '')),
            subset=['guardrail_status']
        ),
        use_container_width=True, hide_index=True
    )
    st.sidebar.markdown("**📥 Export Latest Logs**")
    ac1, ac2, ac3 = st.sidebar.columns(3)
    with ac1:
        st.download_button("CSV", data=export_csv(logs_df_full), file_name="audit_logs.csv", mime="text/csv", use_container_width=True, key="ac1")
    with ac2:
        st.download_button("PDF", data=export_pdf(logs_df_full, "Aegis Audit Logs"), file_name="audit_logs.pdf", mime="application/pdf", use_container_width=True, key="ac2")
    with ac3:
        st.download_button("Word", data=export_docx(logs_df_full, "Aegis Audit Logs"), file_name="audit_logs.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="ac3")
else:
    st.sidebar.info("No audit logs yet.")

if st.sidebar.button("🔄 Refresh Logs"):
    st.rerun()

# ── Main Tabs ─────────────────────────────────────────────────────────────────

tab_chat, tab_explorer, tab_alerts, tab_risk, tab_scenario = st.tabs([
    "💬 Agent Chat",
    "🔍 Product Explorer",
    "⚠️ Predictive Alerts",
    "📊 Supplier Risk",
    "🧪 What-If Planner",
])

# ── Tab 1: Agent Chat ─────────────────────────────────────────────────────────
with tab_chat:
    st.subheader("Agent Communication Console")
    st.caption(f"Session ID: `{st.session_state.session_id}`")

    col_clear, _ = st.columns([1, 5])
    with col_clear:
        if st.button("🗑️ Clear Session"):
            try:
                requests.delete(f"{BACKEND}/api/sessions/{st.session_state.session_id}", timeout=3)
            except Exception:
                pass
            st.session_state.messages = []
            st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("E.g., Check inventory for P001 and simulate a 15-day delay...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.spinner("Aegis is analyzing supply chain data..."):
            try:
                payload = {
                    "query": user_input,
                    "history": st.session_state.messages[:-1],
                    "session_id": st.session_state.session_id,
                }
                res = requests.post(f"{BACKEND}/api/chat", json=payload)
                if res.status_code == 200:
                    agent_response = res.json().get("response", "No response.")
                    st.session_state.messages.append({"role": "assistant", "content": agent_response})
                    with st.chat_message("assistant"):
                        st.markdown(agent_response)
                elif res.status_code == 429:
                    st.warning("⏳ Rate limit reached. Please wait a moment before sending another message.")
                else:
                    st.error(f"Backend returned an error: {res.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("🚨 FastAPI Backend is unreachable. Please ensure it is running on port 8000.")

    st.divider()
    st.markdown("### 🚦 Guardrail Interventions")
    st.info("If the agent was blocked from executing a high-risk action, an admin can authorize an explicit override.")
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🚨 Override Guardrail (Human Approval)", type="primary"):
            with st.spinner("Authorizing override..."):
                override_msg = "I am an authorized admin. I explicitly authorize an override for the previously blocked action. Please execute it immediately and set force_override=True during the tool call."
                st.session_state.messages.append({"role": "user", "content": "*(Admin triggered Override Guardrail)*"})
                try:
                    payload = {
                        "query": override_msg,
                        "history": st.session_state.messages[:-1],
                        "session_id": st.session_state.session_id,
                    }
                    res = requests.post(f"{BACKEND}/api/chat", json=payload)
                    if res.status_code == 200:
                        agent_response = res.json().get("response", "")
                        st.session_state.messages.append({"role": "assistant", "content": agent_response})
                        st.rerun()
                    else:
                        st.error("Backend error during override.")
                except Exception as e:
                    st.error(f"Connection failed: {e}")

# ── Tab 2: Product Explorer ───────────────────────────────────────────────────
with tab_explorer:
    st.subheader("🔍 Advanced Product Explorer")
    with st.expander("Filter Products by Category, Price, or Risk Level", expanded=True):
        c1, c2, c3 = st.columns(3)
        conn = sqlite3.connect("supply_chain.db")
        try:
            categories = ["All"] + pd.read_sql_query("SELECT DISTINCT category FROM Products", conn)["category"].tolist()
            risk_levels = ["All"] + pd.read_sql_query("SELECT DISTINCT risk_level FROM Products WHERE risk_level IS NOT NULL", conn)["risk_level"].tolist()
            max_cost_row = pd.read_sql_query("SELECT MAX(unit_cost) as max_cost FROM Products", conn)
            db_max_cost = int(max_cost_row["max_cost"].iloc[0] or 50000)
        except Exception:
            categories = ["All"]
            risk_levels = ["All", "Low", "Medium", "High", "Critical"]
            db_max_cost = 50000

        with c1:
            sel_cat = st.selectbox("Category", categories, key="search_cat")
        with c2:
            max_price = st.slider("Max Price ($)", 0, max(db_max_cost, 50000), max(db_max_cost, 50000), step=100, key="search_price")
        with c3:
            sel_risk = st.selectbox("Risk Level", risk_levels, key="search_risk")

        query = "SELECT p.*, i.stock, i.reorder_level, i.lead_time_days FROM Products p LEFT JOIN Inventory i ON p.product_id = i.product_id WHERE p.unit_cost <= ?"
        params = [max_price]
        if sel_cat != "All":
            query += " AND p.category = ?"
            params.append(sel_cat)
        if sel_risk != "All":
            query += " AND p.risk_level = ?"
            params.append(sel_risk)

        try:
            results_df = pd.read_sql_query(query, conn, params=params)
            st.dataframe(results_df, use_container_width=True, hide_index=True)
            if not results_df.empty:
                st.markdown("##### 📥 Export Search Results")
                dc1, dc2, dc3 = st.columns(3)
                with dc1:
                    st.download_button("Export CSV", export_csv(results_df), "filtered_search.csv", "text/csv", use_container_width=True, key="sd_csv")
                with dc2:
                    st.download_button("Export PDF", export_pdf(results_df, "Filtered Product Search"), "filtered_search.pdf", "application/pdf", use_container_width=True, key="sd_pdf")
                with dc3:
                    st.download_button("Export Word", export_docx(results_df, "Filtered Product Search"), "filtered_search.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="sd_word")
        except Exception as e:
            st.error(f"Search error: {e}")
        conn.close()

# ── Tab 3: Predictive Stockout Alerts ────────────────────────────────────────
with tab_alerts:
    st.subheader("⚠️ Predictive Stockout Alerts")
    st.markdown("Proactively identifies products at risk of hitting reorder level within your chosen horizon.")

    horizon = st.number_input("Scan Horizon (days)", min_value=1, max_value=365, value=30, step=1, key="horizon_days")

    if st.button("🔍 Scan for Stockout Risks", type="primary"):
        with st.spinner("Scanning inventory..."):
            try:
                res = requests.get(f"{BACKEND}/api/stockout-alerts", params={"horizon_days": int(horizon)}, timeout=10)
                if res.status_code == 200:
                    alerts = res.json()
                    if not alerts:
                        st.success(f"✅ No stockout risk detected within the next {int(horizon)} days.")
                    else:
                        st.warning(f"⚠️ {len(alerts)} product(s) at risk within {int(horizon)} days!")
                        alerts_df = pd.DataFrame(alerts)

                        def color_row(row):
                            if row["estimated_days_until_stockout"] < row["lead_time_days"]:
                                return ["background-color: #ffcccc"] * len(row)
                            return ["background-color: #fff3cd"] * len(row)

                        styled = alerts_df.style.apply(color_row, axis=1)
                        st.dataframe(styled, use_container_width=True, hide_index=True)

                        st.markdown("##### 📥 Export Alerts")
                        ec1, ec2, ec3 = st.columns(3)
                        with ec1:
                            st.download_button("Export CSV", export_csv(alerts_df), "stockout_alerts.csv", "text/csv", use_container_width=True, key="al_csv")
                        with ec2:
                            st.download_button("Export PDF", export_pdf(alerts_df, "Stockout Alerts"), "stockout_alerts.pdf", "application/pdf", use_container_width=True, key="al_pdf")
                        with ec3:
                            st.download_button("Export Word", export_docx(alerts_df, "Stockout Alerts"), "stockout_alerts.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="al_word")
                else:
                    st.error(f"Backend error: {res.status_code} — {res.text}")
            except requests.exceptions.ConnectionError:
                st.error("🚨 FastAPI Backend is unreachable.")

# ── Tab 4: Supplier Risk Dashboard ───────────────────────────────────────────
with tab_risk:
    st.subheader("📊 Supplier Risk Scoring Dashboard")
    st.markdown("Composite risk scores (0–100) per supplier based on location, order failures, and active disruptions.")

    if st.button("🔄 Compute Risk Scores", type="primary"):
        with st.spinner("Computing supplier risk scores..."):
            try:
                payload = {
                    "query": "Compute and show me the risk scores for all suppliers",
                    "history": [],
                    "session_id": None,
                }
                res = requests.post(f"{BACKEND}/api/chat", json=payload, timeout=30)
                if res.status_code == 200:
                    # Also fetch directly from DB for the chart
                    conn = sqlite3.connect("supply_chain.db")
                    try:
                        scores_df = pd.read_sql_query("""
                            SELECT s.name as supplier_name, srs.score, srs.location_sub_score,
                                   srs.failure_sub_score, srs.disruption_sub_score, srs.computed_at
                            FROM SupplierRiskScores srs
                            JOIN Suppliers s ON srs.supplier_id = s.supplier_id
                            ORDER BY srs.computed_at DESC
                        """, conn)
                        conn.close()

                        if not scores_df.empty:
                            # Deduplicate: keep latest score per supplier
                            scores_df = scores_df.drop_duplicates(subset=["supplier_name"], keep="first")

                            st.markdown("#### Risk Score Chart")
                            chart_df = scores_df.set_index("supplier_name")[["score"]]
                            st.bar_chart(chart_df)

                            st.markdown("#### Detailed Scores")
                            def highlight_high_risk(row):
                                if row["score"] > 70:
                                    return ["background-color: #ffcccc; color: #111"] * len(row)
                                return [""] * len(row)

                            styled_scores = scores_df.style.apply(highlight_high_risk, axis=1)
                            st.dataframe(styled_scores, use_container_width=True, hide_index=True)

                            rc1, rc2, rc3 = st.columns(3)
                            with rc1:
                                st.download_button("Export CSV", export_csv(scores_df), "risk_scores.csv", "text/csv", use_container_width=True, key="rs_csv")
                            with rc2:
                                st.download_button("Export PDF", export_pdf(scores_df, "Supplier Risk Scores"), "risk_scores.pdf", "application/pdf", use_container_width=True, key="rs_pdf")
                            with rc3:
                                st.download_button("Export Word", export_docx(scores_df, "Supplier Risk Scores"), "risk_scores.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="rs_word")
                        else:
                            st.info("No risk scores computed yet.")
                    except Exception as e:
                        st.error(f"Could not load scores from DB: {e}")
                else:
                    st.error(f"Backend error: {res.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("🚨 FastAPI Backend is unreachable.")

# ── Tab 5: What-If Scenario Planner ──────────────────────────────────────────
with tab_scenario:
    st.subheader("🧪 What-If Scenario Planner")
    st.markdown("Evaluate the financial and operational impact of a supplier going offline.")

    sc1, sc2 = st.columns(2)
    with sc1:
        scenario_supplier = st.text_input("Supplier ID (e.g., S001)", value="S001", key="sc_supplier")
    with sc2:
        scenario_days = st.number_input("Offline Duration (days)", min_value=1, max_value=365, value=30, step=1, key="sc_days")

    if st.button("🚀 Run Scenario", type="primary"):
        with st.spinner(f"Analyzing impact of {scenario_supplier} going offline for {int(scenario_days)} days..."):
            try:
                payload = {"supplier_id": scenario_supplier, "offline_days": int(scenario_days)}
                res = requests.post(f"{BACKEND}/api/scenario", json=payload, timeout=15)

                if res.status_code == 200:
                    data = res.json()

                    st.info(f"📋 **Scenario Summary:** {data.get('scenario_summary', '')}")

                    col_exp, col_alt = st.columns(2)
                    with col_exp:
                        st.metric("💰 Total Financial Exposure", f"${data.get('total_financial_exposure', 0):,.2f} USD")

                    affected = data.get("affected_products", [])
                    if affected:
                        st.markdown("#### Affected Products")
                        affected_df = pd.DataFrame(affected)
                        st.dataframe(affected_df, use_container_width=True, hide_index=True)

                    alternatives = data.get("recommended_alternatives", [])
                    if alternatives:
                        st.markdown("#### Recommended Alternative Suppliers")
                        alt_df = pd.DataFrame(alternatives)
                        st.dataframe(alt_df, use_container_width=True, hide_index=True)
                    else:
                        st.warning("No alternative suppliers available.")

                    if affected:
                        full_df = pd.DataFrame(affected)
                        sp1, sp2, sp3 = st.columns(3)
                        with sp1:
                            st.download_button("Export CSV", export_csv(full_df), "scenario_results.csv", "text/csv", use_container_width=True, key="sp_csv")
                        with sp2:
                            st.download_button("Export PDF", export_pdf(full_df, "Scenario Analysis"), "scenario_results.pdf", "application/pdf", use_container_width=True, key="sp_pdf")
                        with sp3:
                            st.download_button("Export Word", export_docx(full_df, "Scenario Analysis"), "scenario_results.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key="sp_word")

                elif res.status_code == 404:
                    st.error(f"❌ {res.json().get('detail', 'Supplier not found.')}")
                elif res.status_code == 422:
                    st.error("❌ Invalid input. Check supplier ID and offline days (1-365).")
                else:
                    st.error(f"Backend error: {res.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("🚨 FastAPI Backend is unreachable.")
