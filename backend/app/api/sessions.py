import json

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.db.session import connect
from app.errors import AppError

router = APIRouter(prefix="/sessions")


class SessionIn(BaseModel):
    title: str = Field(default="New chat", max_length=60)


@router.get("")
def list_sessions(request: Request) -> dict:
    with connect(request.app.state.container.settings.db_path) as con:
        rows = con.execute("SELECT id, title, created_at FROM chat_sessions ORDER BY id DESC").fetchall()
    return {"sessions": [dict(r) for r in rows]}


@router.post("", status_code=201)
def create(request: Request, body: SessionIn | None = None) -> dict:
    sid = request.app.state.container.chat.create_session(body.title if body else "New chat")
    return {"id": sid}


@router.delete("/{session_id}", status_code=204)
def delete(request: Request, session_id: int) -> None:
    with connect(request.app.state.container.settings.db_path) as con:
        if con.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,)).rowcount == 0:
            raise AppError("SESSION_NOT_FOUND", "Chat session not found", 404)


@router.get("/{session_id}/messages")
def messages(request: Request, session_id: int, debug: bool = False) -> dict:
    with connect(request.app.state.container.settings.db_path) as con:
        if con.execute("SELECT 1 FROM chat_sessions WHERE id=?", (session_id,)).fetchone() is None:
            raise AppError("SESSION_NOT_FOUND", "Chat session not found", 404)
        rows = con.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
    return {
        "messages": [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "created_at": r["created_at"],
                "citations": json.loads(r["citations_json"]) if r["citations_json"] else None,
                "debug": json.loads(r["debug_json"]) if debug and r["debug_json"] else None,
            }
            for r in rows
        ]
    }
