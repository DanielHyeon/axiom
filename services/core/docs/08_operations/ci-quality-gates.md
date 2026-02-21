# Axiom Core - CI Quality Gates Requirements

## Overview
This document defines the strict Continuous Integration (CI) minimum requirements that every Pull Request against the `core` service must pass before it can be merged.

## 1. Static Analysis & Linting
- **Formatter**: `black` or `ruff` must be used. Code must strictly adhere to the PEP-8 standard length and formatting rules.
- **Linter**: `ruff` must pass with zero errors, catching unused imports and anti-patterns.
- **Type Checking**: `mypy` must run in strict mode (`--strict`). Zero `Any` typings should be allowed in domain and application logic.

## 2. Testing Constraints
- **Unit Testing**: `pytest` must execute all unit tests located in `tests/unit`.
- **Coverage**: Minimum test coverage of **80%** is mandated. Any PR dropping the coverage below this threshold will fail the build.
- **Integration Testing**: Basic DB configuration scripts (`init-db.sql`) must spin up a short-lived PostgreSQL Testcontainer or local docker-compose environment to verify migration scripts (Alembic) apply cleanly.

## 3. Security & Dependency Scanning
- **Vulnerability Audit**: `pip-audit` or `safety` must run to block critical vulnerabilities in transitive Python dependencies.
- **Secret Scanning**: Scanners (e.g., `trufflehog` or GitHub Advanced Security) must ensure no hardcoded secrets (e.g., JWT signatures or AWS keys) are accidentally committed.

## 4. Operational Probes Verification
- The pipeline should contain a dry-run check identifying `startup`, `liveness`, and `readiness` endpoints in the `app/api/health.py` router ensuring Kubernetes deployment manifests in `infra/k8s/` map to the correct probe URLs.

## Conclusion
A failing build on any of these four vectors requires mandatory remediation. Bypassing the CI gates is strictly prohibited for standard feature development.
