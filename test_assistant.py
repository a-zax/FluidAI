from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def post_ask(title: str, payload: dict) -> dict:
    response = client.post("/ask", json=payload)
    print(f"\n{title}")
    print("-" * len(title))
    print("Input:", payload)
    print("Status:", response.status_code)
    data = response.json()
    print("Output:", data)
    assert response.status_code == 200
    return data


def main() -> None:
    normal = post_ask(
        "Normal business query: employee lookup",
        {"question": "Can you find information about employee EMP001?"},
    )
    assert normal["action_performed"] == "fetch_employee"
    assert "Asha Mehta" in normal["answer"]

    follow_up = post_ask(
        "Conversation memory follow-up",
        {
            "question": "What department do they work in?",
            "session_id": normal["session_id"],
        },
    )
    assert follow_up["memory_used"] is True
    assert "Engineering" in follow_up["answer"]

    document_response = client.post(
        "/documents",
        json={
            "title": "VPN Access Policy",
            "body": "VPN access requests require manager approval and IT fulfillment within one business day.",
            "source": "test",
        },
    )
    assert document_response.status_code == 200
    assert document_response.json()["id"].startswith("doc-")

    rag = post_ask(
        "Document retrieval query",
        {"question": "What is the VPN access approval policy?", "enable_actions": False},
    )
    assert "VPN Access Policy" in rag["retrieved_context"]

    challenging = post_ask(
        "Challenging query: high-priority issue requiring confirmation",
        {"question": "I have an urgent issue with the production database. Can you help?"},
    )
    assert challenging["action_performed"] == "pending_confirmation"
    assert challenging["pending_confirmation"]["id"].startswith("PA-")

    confirm_response = client.post(f"/actions/{challenging['pending_confirmation']['id']}/confirm")
    print("\nConfirm pending action")
    print("----------------------")
    print("Status:", confirm_response.status_code)
    print("Output:", confirm_response.json())
    assert confirm_response.status_code == 200
    assert confirm_response.json()["action_performed"] == "create_ticket"
    assert confirm_response.json()["action_result"]["priority"] == "HIGH"

    tickets = client.get("/tickets").json()
    reports = client.get("/reports").json()
    audit = client.get("/audit").json()
    assert tickets["count"] >= 1
    assert "count" in reports
    assert audit["count"] >= 1

    invalid = client.post("/ask", json={"question": " "})
    print("\nInvalid query guardrail")
    print("-----------------------")
    print("Status:", invalid.status_code)
    print("Output:", invalid.json())
    assert invalid.status_code == 422

    print("\nAll demo checks passed.")


if __name__ == "__main__":
    main()
