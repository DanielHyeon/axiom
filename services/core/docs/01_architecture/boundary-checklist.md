# Core Service Boundary Checklist

## Overview
This checklist defines the strict architectural boundaries for the Axiom Core service based on `architecture-overview.md`. Developers must ensure PRs conform to these layered constraints to prevent circular dependencies and architectural degradation.

## 1. Presentation Layer (`app/api/`)
**Responsibilities:** HTTP routing, input validation (Pydantic), output serialization, auth middleware.
- [ ] Are all routes strictly delegating to exactly ONE Application Service?
- [ ] Is there **zero** direct database access (e.g., `db.query()`) within the router?
- [ ] Is there **zero** business logic or state manipulation inside the router?

## 2. Application Layer (`app/services/`)
**Responsibilities:** Use case orchestration, transaction boundaries, event publishing.
- [ ] Does the service strictly coordinate calls between Domain objects and Infrastructure repositories?
- [ ] Are transaction boundaries (e.g., `db.commit()`) managed exclusively here (or via middleware)?
- [ ] Does the service avoid implementing complex domain rules (if/else chains related to business logic)?
- [ ] Are Domain components strictly isolated from Infrastructure dependencies (e.g., injecting data, not repositories, into domain methods)?

## 3. Domain Layer (`app/bpm/`, `app/orchestrator/`)
**Responsibilities:** Core business rules, state transitions, BPM logic, LangGraph flow.
- [ ] Is the code completely agnostic of the database (`SQLAlchemy`, `asyncpg`)?
- [ ] Is the code completely agnostic of external services (HTTP clients, gRPC)?
- [ ] Are state transitions strictly governed by pure functions or encapsulated domain entities?

## 4. Infrastructure Layer (`app/core/`, `app/workers/`)
**Responsibilities:** Database configurations, Redis streams, LLM API calls, Worker lifecycle.
- [ ] Does the code strictly deal with technical concerns (I/O, connection pooling, retries)?
- [ ] Is there **zero** business logic hidden inside SQL queries or Redis consumers?
- [ ] Are all external API calls wrapped with Circuit Breaker and Timeout patterns (default 30s)?

## 5. Module & Inter-Service Isolation
**Responsibilities:** Defining how Core talks to external modules (Vision, Oracle, Synapse).
- [ ] Are all synchronous calls returning within 500ms?
- [ ] Are all heavy/long-running operations (e.g., LLM generation, OCR) delegated to Workers via `event_outbox` / Redis Streams?
- [ ] Does the module recover safely when an external service is down (Fallback paths defined)?
