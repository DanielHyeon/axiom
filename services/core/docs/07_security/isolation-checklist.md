# Multi-tenant Data Isolation Checklist

## Overview
Based on `07_security/data-isolation.md`, this checklist mandates the 4-layer defense-in-depth approach for isolating tenant data within the Axiom Core service.

## 1. Database Level (RLS)
- [ ] Does every new table containing tenant-specific data include a `tenant_id` column?
- [ ] Is Row Level Security (RLS) explicitly enabled (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`)?
- [ ] Are READ/WRITE/UPDATE/DELETE policies defined using `current_setting('app.current_tenant_id')`?
- [ ] Is there a CI or startup script to verify RLS is applied to all applicable tables?

## 2. ORM/Query Level
- [ ] Are all SQLAlchemy models correctly mapped to the `tenant_id` column?
- [ ] Do all ad-hoc SQL queries or ORM calls explicitly include a `WHERE tenant_id = :tenant_id` clause as a redundant safety measure?

## 3. Application State (ContextVar)
- [ ] Is `tenant_id` correctly extracted from the JWT token (or `X-Tenant-Id`/`X-Forwarded-Host`) via middleware?
- [ ] Is `tenant_id` safely stored in a `ContextVar` at the beginning of the request?
- [ ] Do background workers explicitly extract `tenant_id` from the event payload and set it in their local `ContextVar` before accessing the DB?

## 4. Cache & Infrastructure (Redis)
- [ ] Do all Redis cache keys include the `{tenant_id}:` prefix to prevent cross-tenant data leakage?
- [ ] Is there strict enforcement ensuring `tenant_id` is never accepted directly from user input (e.g., JSON request body) to prevent spoofing?
