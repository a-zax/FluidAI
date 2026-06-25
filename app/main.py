import os
import time
import uuid
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.actions import (
    actions_enabled,
    compose_answer,
    confirm_pending_action,
    create_pending_action,
    execute_action,
    requires_confirmation,
    route_action,
)
from app.database import audit_event, fetch_all, from_json
from app.entities import extract_entities
from app.guardrails import contains_forbidden_request
from app.memory import clear_session, conversation_memory, extract_memory_entities, get_history, remember_turn
from app.retrieval import retrieve_documents
from app.schemas import (
    ActionDecision,
    ActionType,
    AskRequest,
    AskResponse,
    ConfirmActionResponse,
    ConversationTurn,
    DocumentRequest,
)
from app.store import store
from app.time_utils import now_iso


app = FastAPI(
    title="Enterprise AI Assistant",
    description="FastAPI enterprise assistant with memory, retrieval, and business action routing.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_model=None)
async def root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"service": "Enterprise AI Assistant", "docs": "/docs"}


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "enterprise_assistant",
        "active_sessions": len(conversation_memory),
        "tickets": len(store.list_tickets()),
        "reports": len(store.list_reports()),
        "documents": len(store.list_documents()),
        "timestamp": now_iso(),
    }


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    start = time.perf_counter()
    session_id = request.session_id or f"session-{uuid.uuid4()}"

    if contains_forbidden_request(request.question):
        raise HTTPException(
            status_code=400,
            detail="The question requests restricted data or unsafe instructions.",
        )

    history = get_history(session_id)
    memory_entities = extract_memory_entities(history)
    current_entities = extract_entities(request.question)
    entities = {**memory_entities, **current_entities}
    memory_used = bool(memory_entities and not current_entities)

    retrieved_docs = retrieve_documents(request.question)
    decision = (
        route_action(request.question, entities)
        if actions_enabled(request.business_action, request.enable_actions)
        else ActionDecision(action=ActionType.NONE, confidence=1.0, reason="Actions disabled.")
    )

    pending_confirmation = None
    if requires_confirmation(decision):
        action_result = create_pending_action(decision, session_id)
        decision = ActionDecision(
            action=ActionType.PENDING_CONFIRMATION,
            parameters=action_result,
            confidence=decision.confidence,
            reason="High-priority action requires confirmation.",
        )
        action_performed = ActionType.PENDING_CONFIRMATION
        pending_confirmation = action_result
    else:
        action_result = execute_action(decision)
        action_performed = decision.action if decision.action != ActionType.NONE else None

    answer = compose_answer(
        retrieved_docs=retrieved_docs,
        decision=decision,
        action_result=action_result,
        entities=entities,
        memory_used=memory_used,
    )

    remember_turn(
        session_id,
        ConversationTurn(
            question=request.question,
            answer=answer,
            entities=entities,
            action_performed=action_performed.value if action_performed else None,
            created_at=now_iso(),
        ),
    )

    audit_event(
        "ask_completed",
        {
            "question": request.question,
            "action": action_performed.value if action_performed else None,
            "memory_used": memory_used,
            "retrieved_context": [doc["title"] for doc in retrieved_docs],
        },
        session_id=session_id,
    )

    return AskResponse(
        answer=answer,
        session_id=session_id,
        action_performed=action_performed,
        action_result=action_result,
        retrieved_context=[doc["title"] for doc in retrieved_docs],
        memory_used=memory_used,
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
        query_type="action_required" if action_performed else "simple_qa",
        tokens_used=len(answer.split()),
        cached=False,
        pending_confirmation=pending_confirmation,
    )


@app.post("/actions/{pending_action_id}/confirm", response_model=ConfirmActionResponse)
async def confirm_action(pending_action_id: str, session_id: str | None = None) -> ConfirmActionResponse:
    try:
        result = confirm_pending_action(pending_action_id, session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConfirmActionResponse(**result)


@app.post("/documents")
async def add_document(request: DocumentRequest) -> Dict[str, Any]:
    return store.add_document(title=request.title, body=request.body, source=request.source)


@app.get("/documents")
async def list_documents() -> Dict[str, Any]:
    documents = store.list_documents()
    return {"count": len(documents), "documents": documents}


@app.get("/tickets")
async def list_tickets() -> Dict[str, Any]:
    tickets = store.list_tickets()
    return {"count": len(tickets), "tickets": tickets}


@app.get("/reports")
async def list_reports() -> Dict[str, Any]:
    reports = store.list_reports()
    return {"count": len(reports), "reports": reports}


@app.get("/audit")
async def list_audit_events(limit: int = 25) -> Dict[str, Any]:
    bounded_limit = max(1, min(limit, 100))
    rows = fetch_all(
        "SELECT id, event_type, session_id, payload_json, created_at FROM audit_events ORDER BY id DESC LIMIT ?",
        (bounded_limit,),
    )
    events = [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "session_id": row["session_id"],
            "payload": from_json(row["payload_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"count": len(events), "events": events}


@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str) -> Dict[str, Any]:
    history = conversation_memory.get(session_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session_id,
        "message_count": len(history),
        "messages": [turn.model_dump() for turn in history],
    }


@app.delete("/sessions/{session_id}")
async def delete_session_history(session_id: str) -> Dict[str, str]:
    if not clear_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "cleared", "session_id": session_id}
