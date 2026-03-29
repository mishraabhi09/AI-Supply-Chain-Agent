@echo off
echo ==============================================
echo 🛡️ Starting Aegis Autonomous Supply Chain Agent
echo ==============================================

echo [1/2] Launching FastAPI Backend on Port 8000...
start cmd /k "python -m uvicorn main:app --reload --port 8000"

echo [2/2] Launching Streamlit Frontend...
timeout /t 3 /nobreak > nul
start cmd /k "python -m streamlit run app.py"

echo.
echo All services are starting up! 
echo If the browser does not open automatically, go to: http://localhost:8501
echo To stop the servers, close the command prompt windows.

