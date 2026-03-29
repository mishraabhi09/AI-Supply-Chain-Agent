import streamlit as st
import requests
import pandas as pd
import sqlite3
from export_utils import export_csv, export_pdf, export_docx
from database import migrate_db

# Run migration to ensure unit_cost and risk_level columns exist
try:
    migrate_db()
except Exception:
    pass

st.set_page_config(page_title="Aegis Supply Chain Agent", layout="wide")

# --- Custom Button Colors via CSS Injection ---
st.markdown("""
<style>
/* ── CSV buttons (green) ─────────────────────────── */
[data-testid="stDownloadButton"]:has(button[data-testid="baseButton-secondary"]) button,
div[data-testid="stDownloadButton"] button {
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
    border: none !important;
}

/* Target by button label text using nth-of-type trick per column group */
/* CSV export buttons — green */
div[data-testid="column"]:nth-child(1) div[data-testid="stDownloadButton"] button {
    background-color: #1a7f4b !important;
    color: #ffffff !important;
}
div[data-testid="column"]:nth-child(1) div[data-testid="stDownloadButton"] button:hover {
    background-color: #15a358 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(26,127,75,0.4) !important;
}

/* PDF export buttons — coral/red */
div[data-testid="column"]:nth-child(2) div[data-testid="stDownloadButton"] button {
    background-color: #c0392b !important;
    color: #ffffff !important;
}
div[data-testid="column"]:nth-child(2) div[data-testid="stDownloadButton"] button:hover {
    background-color: #e74c3c !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(192,57,43,0.4) !important;
}

/* Word export buttons — blue */
div[data-testid="column"]:nth-child(3) div[data-testid="stDownloadButton"] button {
    background-color: #1a56a0 !important;
    color: #ffffff !important;
}
div[data-testid="column"]:nth-child(3) div[data-testid="stDownloadButton"] button:hover {
    background-color: #2874d5 !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(26,86,160,0.4) !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Aegis: Autonomous Supply Chain Resilience Agent")
st.markdown("Monitor disruptions, analyze risk, and execute guarded supply chain decisions.")


# --- Sidebar: Data Management ---
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
                    # Replace the entire table with user's real data
                    df.to_sql(upload_table, conn, if_exists="replace", index=False)
                    conn.close()
                    st.success(f"✅ Successfully updated {upload_table} with {len(df)} rows!")
                except Exception as e:
                    st.error(f"Error uploading data: {e}")

st.sidebar.divider()

# --- Sidebar: Preview Tables ---
with st.sidebar.expander("🔍 Preview Database Data", expanded=False):
    st.info("View the live DataFrames of your SQLite database tables.")
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

# --- Sidebar: Audit Logs ---
st.sidebar.title("📑 Live Audit Logs")
st.sidebar.markdown("Real-time traceability of agent decisions and guardrail interventions.")

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
        use_container_width=True,
        hide_index=True
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

# --- Main App: Advanced Product Search ---
st.subheader("🔍 Advanced Product Explorer")
with st.expander("Filter Products by Category, Price, or Risk Level", expanded=False):
    c1, c2, c3 = st.columns(3)
    conn = sqlite3.connect("supply_chain.db")
    
    # Read distinct categories and risk levels safely
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
        
        # Download buttons for filtered results
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

st.divider()

# --- Main App: Agent Chat ---
st.subheader("Agent Communication Console")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
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
                "history": st.session_state.messages[:-1]
            }
            res = requests.post("http://127.0.0.1:8000/api/chat", json=payload)
            if res.status_code == 200:
                data = res.json()
                agent_response = data.get("response", "No response.")
                
                st.session_state.messages.append({"role": "assistant", "content": agent_response})
                with st.chat_message("assistant"):
                    st.markdown(agent_response)
            else:
                st.error(f"Backend returned an error: {res.status_code}")
        except requests.exceptions.ConnectionError:
            st.error("🚨 FastAPI Backend is unreachable. Please ensure it is running on port 8000.")

st.divider()

# --- Guardrail Override Module ---
st.markdown("### 🚦 Guardrail Interventions")
st.info("If the agent was blocked from executing a high-risk action (like rerouting or exceeding budget), an admin can authorize an explicit override.")

col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🚨 Override Guardrail (Human Approval)", type="primary"):
        with st.spinner("Authorizing override..."):
            override_msg = "I am an authorized admin. I explicitly authorize an override for the previously blocked action. Please execute it immediately and set force_override=True during the tool call."
            st.session_state.messages.append({"role": "user", "content": "*(Admin triggered Override Guardrail)*"})
            
            try:
                payload = {
                    "query": override_msg,
                    "history": st.session_state.messages[:-1]
                }
                res = requests.post("http://127.0.0.1:8000/api/chat", json=payload)
                if res.status_code == 200:
                    agent_response = res.json().get("response", "")
                    st.session_state.messages.append({"role": "assistant", "content": agent_response})
                    st.rerun()
                else:
                    st.error("Backend error during override.")
            except Exception as e:
                 st.error(f"Connection failed: {e}")
