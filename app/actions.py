import uuid
from typing import Any, Dict, List, Optional

from app.database import audit_event, execute, fetch_one, from_json, to_json
from app.retrieval import retrieve_documents
from app.schemas import ActionDecision, ActionType
from app.store import store
from app.time_utils import now_iso


def actions_enabled(business_action: Optional[str], enable_actions: bool) -> bool:
    if business_action is not None:
        return business_action.lower() not in {"false", "0", "off", "none", "disabled"}
    return enable_actions


def route_action(question: str, entities: Dict[str, Any]) -> ActionDecision:
    lowered = question.lower()

    if "employee_id" in entities and any(
        term in lowered for term in ["employee", "who", "department", "email", "contact", "they", "their"]
    ):
        return ActionDecision(
            action=ActionType.FETCH_EMPLOYEE,
            parameters={"employee_id": entities["employee_id"]},
            confidence=0.95,
            reason="Question references an employee record.",
        )

    if any(
        term in lowered
        for term in ["create ticket", "raise ticket", "support ticket", "issue", "not working", "broken", "incident"]
    ):
        return ActionDecision(
            action=ActionType.CREATE_TICKET,
            parameters={
                "topic": infer_ticket_topic(question),
                "description": question,
                "priority": entities.get("priority", "MEDIUM"),
            },
            confidence=0.88,
            reason="Question asks for help with an issue or ticket.",
        )

    if any(term in lowered for term in ["generate report", "report", "summary", "status"]):
        return ActionDecision(
            action=ActionType.GENERATE_REPORT,
            parameters={"report_type": infer_report_type(question)},
            confidence=0.84,
            reason="Question asks for a business report or status summary.",
        )

    if retrieve_documents(question):
        return ActionDecision(
            action=ActionType.QUERY_KNOWLEDGE,
            parameters={},
            confidence=0.72,
            reason="Relevant internal knowledge documents were found.",
        )

    return ActionDecision(action=ActionType.NONE, confidence=0.5, reason="No business action matched.")


def execute_action(decision: ActionDecision) -> Optional[Dict[str, Any]]:
    if decision.action == ActionType.FETCH_EMPLOYEE:
        return store.fetch_employee(decision.parameters["employee_id"])
    if decision.action == ActionType.CREATE_TICKET:
        return store.create_ticket(
            topic=decision.parameters["topic"],
            description=decision.parameters["description"],
            priority=decision.parameters["priority"],
        )
    if decision.action == ActionType.GENERATE_REPORT:
        return store.generate_report(decision.parameters["report_type"])
    if decision.action == ActionType.QUERY_KNOWLEDGE:
        return {"status": "retrieved", "source": "mock_knowledge_base"}
    return None


def requires_confirmation(decision: ActionDecision) -> bool:
    if decision.action == ActionType.CREATE_TICKET:
        return decision.parameters.get("priority") == "HIGH"
    return False


def create_pending_action(decision: ActionDecision, session_id: str) -> Dict[str, Any]:
    pending_id = f"PA-{uuid.uuid4().hex[:10].upper()}"
    pending = {
        "id": pending_id,
        "action": decision.action.value,
        "parameters": decision.parameters,
        "status": "PENDING",
        "reason": "High-priority actions require confirmation before execution.",
        "created_at": now_iso(),
    }
    execute(
        """
        INSERT INTO pending_actions (id, action, parameters_json, status, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            pending["id"],
            pending["action"],
            to_json(pending["parameters"]),
            pending["status"],
            pending["reason"],
            pending["created_at"],
        ),
    )
    audit_event("pending_action_created", pending, session_id=session_id)
    return pending


def confirm_pending_action(pending_action_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    row = fetch_one("SELECT * FROM pending_actions WHERE id = ?", (pending_action_id,))
    if not row:
        raise ValueError("Pending action not found")
    if row["status"] != "PENDING":
        raise ValueError(f"Pending action is already {row['status']}")

    decision = ActionDecision(
        action=ActionType(row["action"]),
        parameters=from_json(row["parameters_json"]),
        confidence=1.0,
        reason="Confirmed by user.",
    )
    result = execute_action(decision)
    execute(
        "UPDATE pending_actions SET status = ?, confirmed_at = ? WHERE id = ?",
        ("CONFIRMED", now_iso(), pending_action_id),
    )
    audit_event(
        "pending_action_confirmed",
        {"pending_action_id": pending_action_id, "action": decision.action.value, "result": result},
        session_id=session_id,
    )
    return {
        "pending_action_id": pending_action_id,
        "action_performed": decision.action,
        "action_result": result or {},
        "status": "CONFIRMED",
    }


def compose_answer(
    retrieved_docs: List[Dict[str, str]],
    decision: ActionDecision,
    action_result: Optional[Dict[str, Any]],
    entities: Dict[str, Any],
    memory_used: bool,
) -> str:
    if decision.action == ActionType.FETCH_EMPLOYEE and action_result:
        if not action_result["found"]:
            return (
                f"I could not find {action_result['employee_id']} in the mock employee directory. "
                "Please check the employee ID and try again."
            )
        employee = action_result["employee"]
        memory_note = " using the employee from our previous turn" if memory_used else ""
        return (
            f"I found {action_result['employee_id']}{memory_note}: {employee['name']} is a "
            f"{employee['role']} in {employee['department']}. Contact: {employee['email']}. "
            f"Location: {employee['location']}."
        )

    if decision.action == ActionType.CREATE_TICKET and action_result:
        return (
            f"I created support ticket {action_result['id']} for '{action_result['topic']}'. "
            f"Priority is {action_result['priority']} with an SLA of {action_result['sla_hours']} hours. "
            "I used the request text as the ticket description so the support team has the original context."
        )

    if decision.action == ActionType.PENDING_CONFIRMATION and action_result:
        return (
            f"I prepared a {action_result['action'].replace('_', ' ')} request but did not execute it yet. "
            f"Confirmation is required because this is high priority. Pending action: {action_result['id']}."
        )

    if decision.action == ActionType.GENERATE_REPORT and action_result:
        summary = action_result["summary"]
        return (
            f"I generated {action_result['type']} report {action_result['id']}. "
            f"It shows {summary['employee_records']} employee records, {summary['open_tickets']} open tickets, "
            f"and {summary['high_priority_tickets']} high priority tickets. "
            f"Recommendation: {action_result['recommendation']}"
        )

    if retrieved_docs:
        context = " ".join(f"{doc['title']}: {doc['body']}" for doc in retrieved_docs)
        return f"Based on the internal knowledge base, {context}"

    if "employee_id" in entities:
        return (
            f"I see a reference to {entities['employee_id']}, but I need a clearer request. "
            "Ask for the employee's department, email, or profile and I can fetch it."
        )

    return (
        "I can help with employee lookup, ticket creation, report generation, and internal knowledge queries. "
        "Try asking 'Who is EMP001?' or 'Create a ticket for a production database issue.'"
    )


def infer_ticket_topic(question: str) -> str:
    lowered = question.lower()
    if "database" in lowered or "db" in lowered:
        return "Database access or reliability issue"
    if "login" in lowered or "access" in lowered:
        return "Login or access issue"
    if "production" in lowered or "incident" in lowered:
        return "Production incident"
    return "General support issue"


def infer_report_type(question: str) -> str:
    lowered = question.lower()
    if "ticket" in lowered or "support" in lowered:
        return "ticket_operations"
    if "employee" in lowered or "people" in lowered:
        return "employee_directory"
    return "operations_summary"
