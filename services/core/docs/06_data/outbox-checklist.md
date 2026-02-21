# Event Outbox & Streams Boundary Checklist

## Overview
Based on `06_data/event-outbox.md`, this checklist enforces safe event publishing via the Outbox pattern and reliable consuming via Redis Streams.

## 1. Publishing Events (Outbox Pattern)
- [ ] Are all domain events inserted into the `event_outbox` table within the **SAME** database transaction as the business entity changes?
- [ ] Is there **zero** direct calling of `redis.publish` or external HTTP APIs inside synchronous business transaction flows?
- [ ] Does the `event_outbox` schema include `tenant_id` for downstream context propagation?

## 2. Consuming Events (Workers)
- [ ] Is the worker explicitly utilizing Redis Consumer Groups to distribute load?
- [ ] Are all event handlers strictly **idempotent** (e.g., using Redis `SETNX` with an expiration to deduplicate by `event_id`)?
- [ ] Does the worker safely reset its `ContextVar` tenant context based on the incoming event payload before interacting with the database?

## 3. Resilience & Maintenance
- [ ] Is there a retry mechanism (e.g., recovering pending messages older than 5 minutes via `XCLAIM`) for crashed consumers?
- [ ] Are Dead Letter Queue (DLQ) triggers implemented for events that persistently fail after multiple retries?
- [ ] Is there a maintenance job (e.g., `pg_cron`) securely purging successfully processed events from the `event_outbox` table?
