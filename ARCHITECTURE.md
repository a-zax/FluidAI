# Architecture

## System Goal

The project is an end-to-end enterprise assistant. It combines a chat UI, FastAPI backend, deterministic agent-style routing, lightweight retrieval, approval-gated actions, SQLite persistence, and audit logging.

## Runtime Flow

```mermaid
flowchart TD
    A[User] --> B[Claude-inspired chat UI]
    B --> C[POST /ask]
    C --> D[Validate request]
    D --> E[Guardrail check]
    E --> F[Load session memory]
    F --> G[Extract entities]
    G --> H[Retrieve documents]
    H --> I[Route intent]
    I --> J{Tool decision}
    J --> K[fetch_employee]
    J --> L[create_ticket]
    J --> M[generate_report]
    J --> N[query_knowledge]
    L --> O{High priority?}
    O -->|Yes| P[Store pending action]
    O -->|No| Q[Create ticket]
    K --> R[Compose answer]
    M --> R
    N --> R
    P --> R
    Q --> R
    R --> S[Write audit event]
    S --> T[Return JSON response]
```

## Confirmation Workflow

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant API
    participant DB as SQLite

    User->>UI: Ask for urgent production database help
    UI->>API: POST /ask
    API->>API: Detect create_ticket + HIGH priority
    API->>DB: INSERT pending_actions
    API->>DB: INSERT audit_events
    API-->>UI: pending_confirmation with PA id
    User->>UI: Confirm action
    UI->>API: POST /actions/{id}/confirm
    API->>DB: Read pending action
    API->>DB: INSERT ticket
    API->>DB: UPDATE pending action
    API->>DB: INSERT audit event
    API-->>UI: Ticket result
```

## Package Layout

```mermaid
flowchart LR
    Main[app/main.py<br/>Routes and orchestration]
    Schemas[app/schemas.py<br/>API contracts]
    Actions[app/actions.py<br/>Intent routing and tools]
    Store[app/store.py<br/>Enterprise data access]
    DB[app/database.py<br/>SQLite layer]
    Retrieval[app/retrieval.py<br/>Document search]
    Memory[app/memory.py<br/>Session memory]
    Guardrails[app/guardrails.py<br/>Safety filters]
    Entities[app/entities.py<br/>Entity extraction]
    UI[static/*<br/>Chat frontend]

    UI --> Main
    Main --> Schemas
    Main --> Actions
    Main --> Retrieval
    Main --> Memory
    Main --> Guardrails
    Main --> Entities
    Actions --> Store
    Retrieval --> Store
    Store --> DB
```

## Persistence Model

```mermaid
erDiagram
    TICKETS {
        string id
        string topic
        string description
        string priority
        string status
        string requester
        string created_at
        int sla_hours
    }

    REPORTS {
        string id
        string type
        string summary_json
        string recommendation
        string generated_at
    }

    DOCUMENTS {
        string id
        string title
        string body
        string source
        string created_at
    }

    PENDING_ACTIONS {
        string id
        string action
        string parameters_json
        string status
        string reason
        string created_at
        string confirmed_at
    }

    AUDIT_EVENTS {
        int id
        string event_type
        string session_id
        string payload_json
        string created_at
    }
```

## Key Design Decisions

- **Deterministic routing instead of mandatory hosted LLM:** Keeps the demo reliable and free to run.
- **SQLite over in-memory state:** Demonstrates production direction without requiring a separate database service.
- **Approval before high-priority ticket execution:** Shows enterprise control and risk management.
- **Document ingestion as JSON:** Avoids extra parser dependencies while still demonstrating RAG-style retrieval.
- **In-memory conversation memory:** Good for demo speed; Redis would be the production replacement.

## Upgrade Path

```mermaid
flowchart TD
    A[Current demo] --> B[Add optional LLM planner]
    B --> C[Add embeddings + vector DB]
    C --> D[Add authentication]
    D --> E[Add role-based access control]
    E --> F[Deploy with Postgres + Redis]
```
