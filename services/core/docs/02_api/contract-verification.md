# API Contract Verification Report (Sprint 1)

## Overview
This document verifies the API contracts described in `gateway-api.md`, `process-api.md`, and `watch-api.md` to ensure they align structurally and semantically with the Axiom Canvas frontend definitions.

## 1. Gateway Routing Checks
- [x] All routes correctly map to `/api/v1/*`.
- [x] FastAPI middleware correctly replicates K-AIR's Spring Cloud Gateway filters (JWT, tenant extraction via `X-Forwarded-Host`).
- [x] Rate limiting is granular (`/auth/login` = 10/min, default = 100/min).
- [x] CORS is strictly whitelisted (`allow_origins !== ["*"]`).

## 2. Process API Checks (`/api/v1/process/*`)
- [x] `POST /initiate` properly accepts `proc_def_id` and initial payload.
- [x] `POST /submit` handles `result_data` and advances the workflow.
- [x] `POST /approve-hitl` and `POST /rework` correctly mandate feedback strings on negative actions.
- [x] Workitem states (`TODO`, `IN_PROGRESS`, `SUBMITTED`, `DONE`, `REWORK`, `CANCELLED`) properly match the UI filter configurations in `apps/canvas/`.

## 3. Watch API Checks (`/api/v1/watches/*`)
- [x] Subscriptions explicitly bind to an `event_type` and ruleset (deadline, threshold, pattern).
- [x] `GET /stream` (SSE) appropriately handles real-time alerts.
- [x] Role-based seed subscriptions are mandated on user creation.
- [x] `PUT /read-all` bulk operation exists for reducing unread notification loads.

## Conclusion
The API contracts reflect a standardized REST architecture augmented by SSEs for live streams. They are cleared for implementation in subsequent sprints.

## 4. Cross-Service Contract Checks (2026-02-22)
- [x] Core Gateway `graph/ontology` proxy routes map to Synapse v3 paths and preserve tenant headers.
- [x] Live HTTP E2E validated for Core -> Synapse (`tests/integration/test_e2e_gateway_graph_ontology_live.py`).
- [x] Live HTTP E2E validated for Core -> Synapse EventLog/ProcessMining proxy routes (`tests/integration/test_e2e_gateway_eventlog_mining_live.py`).
- [x] Live HTTP E2E validated for Core -> Synapse Extraction/Schema-Edit proxy routes (`tests/integration/test_e2e_gateway_extraction_schema_live.py`).
- [x] Live HTTP E2E validated for Oracle -> Synapse(meta) and Oracle -> Core(events/watch-agent) (`services/oracle/tests/integration/test_cross_service_contract_live.py`).
