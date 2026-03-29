# 🛡️ Aegis: Autonomous Supply Chain Resilience Agent

Aegis is an intelligent, autonomous AI agent built to monitor supply chain disruptions, analyze catalog risks, and execute guarded supply chain decisions like rerouting shipments or autonomously placing purchase orders. 

The system leverages a functional **LangChain ReAct** architecture backed by a **FastAPI** backend and a **Streamlit** frontend, allowing users to converse naturally with their supply chain database. 

## 🚀 Features
- **Multi-LLM Support**: Supports routing your agent's brain through Google (Gemini), OpenAI (GPT), or Groq (LLaMA) via a dynamic `.env` configuration.
- **Natural Language Data Explorer**: Query your internal catalog, stock levels, and supply chain telemetry entirely out of natural language.
- **Ripple Effect Simulation**: Simulates the downstream cascading impact of a delayed shipment (e.g., calculates days until a potential factory production halt).
- **Disruption Intel Feed**: Integrates external web/news simulation to assess location-based disruption risks (like port strikes).
- **Autonomous Action Execution**: The agent isn't just a chatbot; it actively modifies the database by calling tools to create purchase orders and restructure shipments.
- **Strict Guardrails**: Hardcoded heuristics automatically block the agent if it attempts an order >$10k, buys from a restricted/sanctioned geofence, or tries to execute high-risk reroutes.
- **Human-in-the-Loop Override**: Any action blocked by Aegis's guardrails halts the agent execution until an admin presses the physical *Override* button in the UI.
- **Auditing & Live Traces**: Every tool execution, AI thought, and guardrail evaluation is logged to an SQLite Audit Log, viewable and exportable (CSV/PDF/Word) in real-time.

---

## 📂 Project Architecture

The core responsibilities are split up exactly as follows:

| File | Purpose |
|------|---------|
| `app.py` | The main **Streamlit** frontend interface. Houses the Agent Communication Console, the data uploader, and the Audit logs panel. |
| `main.py` | The **FastAPI** backend core. Exposes REST API routes so the frontend can dispatch queries to the LangChain engine asynchronously. |
| `agent.py` | The **LangChain** orchestrator. Defines the system prompt, registers all the available AI tools, loads the selected LLM, and manages the execution loop. |
| `tools.py` | Python tool execution logic (`create_purchase_order`, `simulate_ripple_effect`, `check_global_news`, `query_database`, etc.). |
| `guardrails.py` | Hardcoded algorithmic rules mapping constraint logic against AI action inputs (e.g. `validate_order_cost`, `validate_supplier_location`). |
| `database.py` | The local **SQLite** database initialization script. Bootstraps Tables (Products, Inventory, Suppliers, Orders, Events, AuditLogs) and sample data. |

---

## 🌐 API Routes (FastAPI)

Behind the scenes, the Streamlit app interacts with the agent using these exposed routes located in `main.py`:

* `GET /`
  * **Description**: Simple root endpoint greeting. Returns a welcome message.
* `GET /health`
  * **Description**: Returns `{"status": "healthy"}`. Used to ping the server.
* `POST /api/chat`
  * **Payload**: `{"query": "your prompt string", "history": [ {}, {} ]}`
  * **Description**: The primary conversational endpoint. Receives the user prompt and previous conversational memory, hands it over to the LangChain executor, blocks until the agent finishes processing its internal tools, and returns the final LLM response as a string.

---

## 🛠Dependencies & Installation

The project runs on Python. Its core libraries are detailed in `requirements.txt`:
* **Web Serving**: `fastapi`, `uvicorn`, `streamlit`
* **AI Orchestration**: `langchain`, `langchain-google-genai`, `langchain-openai`, `langchain-groq`
* **Data Processing**: `pydantic`
* **Environment Handling**: `python-dotenv`

### 1. Setup Environment
Create a `.env` file at the root of the project to hold your API keys. Select which provider the agent should use natively:

```env
# Set the active LLM provider ('gemini', 'openai', or 'groq')
ACTIVE_LLM=gemini

GOOGLE_API_KEY=your_google_key
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
```

### 2. Install Packages
Run the following inside your terminal to install prerequisites:
```bash
pip install -r requirements.txt
```

---

## 🏁 How to Run

Because the project relies on a decoupled Client (Streamlit) and Server (FastAPI), **both must be running simultaneously**.


**Option 1: The Quick Start (Windows)**
Simply run the included batch script. This will open two separate command prompts, execute both processes, and launch your browser!
```cmd
run.bat
```

**Option 2: Manual Start**
If you prefer manual control, open two concurrent terminal windows in the project directory:

**Terminal Window 1: Start the Backend**
```bash
python -m uvicorn main:app --reload --port 8000
```
**Terminal Window 2: Start the Frontend**
```bash
python -m streamlit run app.py
```

The application UI will now be available locally at `http://localhost:8501`.
