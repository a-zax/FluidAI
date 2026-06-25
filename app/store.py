import uuid
from typing import Any, Dict, List

from app.database import audit_event, execute, fetch_all, fetch_one, from_json, to_json
from app.time_utils import now_iso


DEFAULT_DOCUMENTS = [
    {
        "id": "kb-onboarding",
        "title": "Employee Onboarding SLA",
        "body": (
            "Engineering onboarding tickets should be acknowledged within 4 business hours. "
            "Access requests require manager approval and then move to IT fulfillment."
        ),
        "source": "seed",
    },
    {
        "id": "kb-incident",
        "title": "Production Incident Workflow",
        "body": (
            "High priority production issues create an incident ticket, notify the platform owner, "
            "and require a timeline update every 30 minutes until mitigation."
        ),
        "source": "seed",
    },
    {
        "id": "kb-reports",
        "title": "Monthly Operations Report",
        "body": (
            "Operations reports summarize open tickets, SLA risk, employee lookup volume, "
            "and resolved workflow actions for leadership review."
        ),
        "source": "seed",
    },
]


class EnterpriseStore:
    def __init__(self) -> None:
        self.employees: Dict[str, Dict[str, str]] = {
            "EMP001": {
                "name": "Asha Mehta",
                "department": "Engineering",
                "role": "Platform Lead",
                "email": "asha.mehta@fluidai.example",
                "location": "Mumbai",
            },
            "EMP002": {
                "name": "Rohan Iyer",
                "department": "Sales",
                "role": "Enterprise Account Manager",
                "email": "rohan.iyer@fluidai.example",
                "location": "Bengaluru",
            },
            "EMP003": {
                "name": "Naina Shah",
                "department": "People Ops",
                "role": "HR Business Partner",
                "email": "naina.shah@fluidai.example",
                "location": "Mumbai",
            },
        }
        self.seed_documents()

    def seed_documents(self) -> None:
        for doc in DEFAULT_DOCUMENTS:
            existing = fetch_one("SELECT id FROM documents WHERE id = ?", (doc["id"],))
            if existing:
                continue
            execute(
                "INSERT INTO documents (id, title, body, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (doc["id"], doc["title"], doc["body"], doc["source"], now_iso()),
            )

    @property
    def knowledge_docs(self) -> List[Dict[str, str]]:
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "body": row["body"],
                "source": row["source"],
                "created_at": row["created_at"],
            }
            for row in fetch_all("SELECT id, title, body, source, created_at FROM documents ORDER BY created_at ASC")
        ]

    def add_document(self, title: str, body: str, source: str = "user") -> Dict[str, Any]:
        existing = fetch_one("SELECT id, title, body, source, created_at FROM documents WHERE title = ? AND body = ?", (title, body))
        if existing:
            return dict(existing)

        doc_id = f"doc-{uuid.uuid4().hex[:10]}"
        document = {
            "id": doc_id,
            "title": title,
            "body": body,
            "source": source,
            "created_at": now_iso(),
        }
        execute(
            "INSERT INTO documents (id, title, body, source, created_at) VALUES (?, ?, ?, ?, ?)",
            (document["id"], document["title"], document["body"], document["source"], document["created_at"]),
        )
        audit_event("document_added", {"document_id": doc_id, "title": title, "source": source})
        return document

    def list_documents(self) -> List[Dict[str, Any]]:
        return self.knowledge_docs

    def fetch_employee(self, employee_id: str) -> Dict[str, Any]:
        normalized_id = employee_id.upper()
        employee = self.employees.get(normalized_id)
        if not employee:
            return {
                "found": False,
                "employee_id": normalized_id,
                "message": "No employee matched that ID in the mock directory.",
            }
        return {"found": True, "employee_id": normalized_id, "employee": employee}

    def create_ticket(
        self,
        topic: str,
        description: str,
        priority: str = "MEDIUM",
        requester: str = "api-user",
    ) -> Dict[str, Any]:
        count = fetch_one("SELECT COUNT(*) AS count FROM tickets")["count"]
        ticket_id = f"TICKET-{1000 + int(count) + 1}"
        ticket = {
            "id": ticket_id,
            "topic": topic,
            "description": description,
            "priority": priority,
            "status": "OPEN",
            "requester": requester,
            "created_at": now_iso(),
            "sla_hours": 8 if priority == "HIGH" else 24,
        }
        execute(
            """
            INSERT INTO tickets (id, topic, description, priority, status, requester, created_at, sla_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket["id"],
                ticket["topic"],
                ticket["description"],
                ticket["priority"],
                ticket["status"],
                ticket["requester"],
                ticket["created_at"],
                ticket["sla_hours"],
            ),
        )
        audit_event("ticket_created", ticket)
        return ticket

    def list_tickets(self) -> List[Dict[str, Any]]:
        return fetch_all("SELECT * FROM tickets ORDER BY created_at DESC")

    def generate_report(self, report_type: str) -> Dict[str, Any]:
        count = fetch_one("SELECT COUNT(*) AS count FROM reports")["count"]
        report_id = f"REPORT-{int(count) + 1:03d}"
        ticket_stats = fetch_one(
            """
            SELECT
                COUNT(*) AS open_tickets,
                SUM(CASE WHEN priority = 'HIGH' THEN 1 ELSE 0 END) AS high_priority_tickets
            FROM tickets
            WHERE status = 'OPEN'
            """
        )
        document_count = fetch_one("SELECT COUNT(*) AS count FROM documents")["count"]
        summary = {
            "employee_records": len(self.employees),
            "open_tickets": int(ticket_stats["open_tickets"] or 0),
            "high_priority_tickets": int(ticket_stats["high_priority_tickets"] or 0),
            "knowledge_documents": int(document_count),
        }
        report = {
            "id": report_id,
            "type": report_type,
            "generated_at": now_iso(),
            "summary": summary,
            "recommendation": (
                "Review high priority tickets first and use employee directory lookups "
                "to route ownership quickly."
            ),
        }
        execute(
            "INSERT INTO reports (id, type, summary_json, recommendation, generated_at) VALUES (?, ?, ?, ?, ?)",
            (report["id"], report["type"], to_json(summary), report["recommendation"], report["generated_at"]),
        )
        audit_event("report_generated", report)
        return report

    def list_reports(self) -> List[Dict[str, Any]]:
        reports = fetch_all("SELECT * FROM reports ORDER BY generated_at DESC")
        return [
            {
                "id": row["id"],
                "type": row["type"],
                "summary": from_json(row["summary_json"]),
                "recommendation": row["recommendation"],
                "generated_at": row["generated_at"],
            }
            for row in reports
        ]


store = EnterpriseStore()
