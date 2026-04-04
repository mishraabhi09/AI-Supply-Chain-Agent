"""
Session Store
Persists chat history to SQLite so users can resume conversations across browser sessions.
"""
from datetime import datetime
from database import get_connection


def save_message(session_id: str, role: str, content: str) -> None:
    """Inserts a chat message into ChatSessions."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ChatSessions (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_history(session_id: str) -> list[dict]:
    """Returns all messages for a session ordered by timestamp ASC."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, timestamp FROM ChatSessions WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]


def delete_session(session_id: str) -> None:
    """Deletes all messages for the given session_id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ChatSessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
