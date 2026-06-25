from typing import Any, Dict, List

from app.schemas import ConversationTurn


conversation_memory: Dict[str, List[ConversationTurn]] = {}


def get_history(session_id: str) -> List[ConversationTurn]:
    return conversation_memory.setdefault(session_id, [])


def remember_turn(session_id: str, turn: ConversationTurn) -> None:
    history = conversation_memory.setdefault(session_id, [])
    history.append(turn)
    conversation_memory[session_id] = history[-10:]


def clear_session(session_id: str) -> bool:
    if session_id not in conversation_memory:
        return False
    del conversation_memory[session_id]
    return True


def extract_memory_entities(history: List[ConversationTurn]) -> Dict[str, Any]:
    for turn in reversed(history):
        if "employee_id" in turn.entities:
            return {"employee_id": turn.entities["employee_id"]}
    return {}
