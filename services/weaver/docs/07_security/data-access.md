# Weaver - 데이터 접근 제어 및 테넌트 격리

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **근거**: Core auth-model.md, connection-security.md

<!-- affects: 02_api, 03_backend -->

---

## 이 문서가 답하는 질문

- Weaver에서 역할/권한 기반 접근 제어는 어떻게 동작하는가?
- 데이터소스 관리 및 메타데이터에 대한 테넌트 격리는?
- 어떤 역할이 어떤 API에 접근 가능한가?

---

## 1. 인증 모델

### 1.1 JWT 토큰 검증

Weaver는 Axiom Core의 JWT 인증 미들웨어를 사용한다 (connection-security.md §7 참조).

```python
# JWT verification (from Axiom Core)
from axiom_core.security import require_auth, require_role

@router.post("/datasources")
@require_role("admin", "engineer")
async def create_datasource(
    body: DataSourceCreate,
    current_user: User = Depends(require_auth),
):
    ...
```

### 1.2 역할 기반 접근 제어 (RBAC)

Weaver는 Core 시스템 역할을 직접 사용한다 (Core auth-model.md §5.1 참조).

| Core 시스템 역할 | Weaver 권한 |
|-----------------|-------------|
| admin | 전체 — 데이터소스 CRUD, 인트로스펙션, 스냅샷, 용어 사전 관리 |
| engineer | 데이터소스 CRUD, 인트로스펙션, 스냅샷, 용어 사전 관리 |
| manager | 메타데이터 읽기, 스냅샷 조회 |
| attorney | 메타데이터 읽기 |
| analyst | 메타데이터 읽기 |
| staff | 메타데이터 읽기 |
| viewer | 메타데이터 읽기 |

### 1.3 API별 접근 제어 매트릭스

| API | admin | engineer | manager | attorney/analyst/staff | viewer |
|-----|:-----:|:--------:|:-------:|:---------------------:|:------:|
| 데이터소스 생성 | O | O | X | X | X |
| 데이터소스 수정 | O | O | X | X | X |
| 데이터소스 삭제 | O | X | X | X | X |
| 데이터소스 목록 조회 | O | O | O | O | O |
| 인트로스펙션 실행 | O | O | X | X | X |
| 메타데이터 조회 | O | O | O | O | O |
| 스냅샷 생성 | O | O | X | X | X |
| 스냅샷 비교 (Diff) | O | O | O | X | X |
| 스냅샷 조회 | O | O | O | O | O |
| 용어 사전 관리 | O | O | X | X | X |
| 용어 사전 조회 | O | O | O | O | O |

---

## 2. 테넌트 격리

### 2.1 Neo4j 테넌트 격리

Weaver가 소유하는 모든 Neo4j 노드에는 `tenant_id`가 포함된다 (neo4j-schema-v2.md 참조). 모든 쿼리에 필터를 적용한다.

```cypher
// CORRECT: tenant_id 필터 포함
MATCH (t:Table {tenant_id: $tenant_id})
RETURN t

MATCH (snap:FabricSnapshot {tenant_id: $tenant_id})
RETURN snap ORDER BY snap.created_at DESC LIMIT 1

// FORBIDDEN: tenant_id 없이 쿼리
MATCH (t:Table)
RETURN t
```

### 2.2 대상 DB 연결 격리

각 데이터소스 연결 정보는 테넌트별로 격리된다. MindsDB에 등록할 때 테넌트 접두어를 사용한다.

```python
# 데이터소스 이름에 tenant_id 접두어
datasource_name = f"{tenant_id}_{datasource.name}"
```

### 2.3 API 미들웨어

```python
# tenant_id는 JWT에서만 추출 (사용자 입력 금지)
@app.middleware("http")
async def set_tenant_context(request: Request, call_next):
    user = request.state.user  # From JWT
    request.state.tenant_id = user.tenant_id
    return await call_next(request)
```

---

## 3. 감사 로깅

connection-security.md §8의 감사 로깅 정책을 따른다.

---

## 금지 사항 (Forbidden)

- tenant_id 없이 Neo4j 쿼리 실행
- 다른 테넌트의 데이터소스에 접근
- 데이터소스 비밀번호를 로그/API 응답에 포함 (connection-security.md §2 참조)
- 사용자 입력에서 tenant_id를 받기 (JWT에서만 추출)

## 필수 사항 (Required)

- 모든 Weaver API에 JWT 검증 적용
- 모든 Neo4j 쿼리에 `tenant_id` 파라미터 포함
- 데이터소스 관리 API에 `admin` 또는 `engineer` 역할 필수
- 비밀번호 필터링 (connection-security.md §2.3)

## 관련 문서

- [connection-security.md](connection-security.md): DB 연결 보안, 비밀번호 관리
- Core auth-model.md: JWT 인증 모델, 시스템 역할 SSOT
- neo4j-schema-v2.md: Weaver Neo4j 스키마 (테넌트 격리 포함)
