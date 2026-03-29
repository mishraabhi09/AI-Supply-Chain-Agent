from fastapi import FastAPI
from pydantic import BaseModel
from agent import chat_with_aegis

app = FastAPI(
    title="Aegis Autonomous Supply Chain Resilience Agent",
    description="API for managing supply chain resilience via AI agent.",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    query: str
    history: list = []

class ChatResponse(BaseModel):
    response: str
    actions: list = []

@app.get("/")
def read_root():
    return {"message": "Welcome to Aegis API. The system is running."}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/chat", response_model=ChatResponse)
def chat_with_agent(request: ChatRequest):
    result = chat_with_aegis(request.query, request.history)
    return ChatResponse(
        response=result.get("response", "Error processing request."),
        actions=result.get("actions", [])
    )

