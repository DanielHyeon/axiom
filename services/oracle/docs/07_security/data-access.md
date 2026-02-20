# Oracle - 데이터 접근 제어 및 테넌트 격리

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **근거**: Core auth-model.md, sql-safety.md

<!-- affects: 02_api, 03_backend -->

---

## 이 문서가 답하는 질문

- Oracle에서 역할/권한 기반 접근 제어는 어떻게 동작하는가?
- NL2SQL 결과에서 테넌트 격리는 어떻게 보장하는가?
- 어떤 역할이 어떤 API에 접근 가능한가?

---

## 1. 인증 모델

### 1.1 JWT 토큰 검증

Oracle은 자체 인증을 수행하지 않는다. Axiom Core가 발급한 JWT를 검증만 한다.

```python
# Oracle JWT dependency (Core auth-model.md SSOT 참조)
async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> CurrentUser:
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    return CurrentUser(
        user_id=UUID(payload["sub"]),
        tenant_id=UUID(payload["tenant_id"]),
        role=payload["role"],
        permissions=payload.get("permissions", []),
    )
```

### 1.2 역할 기반 접근 제어 (RBAC)

Oracle은 Core 시스템 역할을 직접 사용한다 (Core auth-model.md §5.1 참조).

| Core 시스템 역할 | Oracle 권한 |
|-----------------|-------------|
| admin | 전체 — SQL Guard 관리, 화이트리스트 수정, 직접 SQL 실행 |
| manager | NL2SQL 쿼리, 쿼리 결과 조회 |
| attorney | NL2SQL 쿼리, 쿼리 결과 조회 |
| analyst | NL2SQL 쿼리, 쿼리 결과 조회 |
| engineer | NL2SQL 쿼리, 스키마 메타데이터 조회 |
| staff | 읽기 전용 (결과 조회만) |
| viewer | 읽기 전용 (결과 조회만) |

### 1.3 API별 접근 제어 매트릭스

| API | admin | manager | attorney | analyst | engineer | staff | viewer |
|-----|:-----:|:-------:|:--------:|:-------:|:--------:|:-----:|:------:|
| NL2SQL 질의 | O | O | O | O | O | X | X |
| 직접 SQL 실행 | O | X | X | X | X | X | X |
| 쿼리 결과 조회 | O | O | O | O | O | O | O |
| 쿼리 히스토리 | O | O | O | O | O | O | O |
| 스키마 메타데이터 조회 | O | O | O | O | O | O | O |
| SQL Guard 설정 변경 | O | X | X | X | X | X | X |
| 화이트리스트 관리 | O | X | X | X | X | X | X |

---

## 2. 테넌트 격리

### 2.1 NL2SQL 쿼리의 tenant_id 격리

Oracle이 생성/실행하는 모든 SQL에는 `tenant_id` 필터가 포함되어야 한다.

```python
# NL2SQL 파이프라인에서 tenant_id 주입
async def execute_nl2sql(
    question: str,
    user: CurrentUser,
    datasource_id: str,
) -> QueryResult:
    # 1. LLM이 SQL 생성
    generated_sql = await generate_sql(question, datasource_id)

    # 2. SQL Guard 검증 (sql-safety.md 참조)
    validated_sql = sql_guard.validate(generated_sql)

    # 3. tenant_id 필터 주입 (파라미터 바인딩)
    # 생성된 SQL의 대상 테이블에 RLS가 적용되어 있으므로
    # DB 세션의 GUC 변수 설정으로 격리
    async with get_readonly_session() as db:
        await db.execute(
            text("SET LOCAL app.current_tenant_id = :tenant_id"),
            {"tenant_id": str(user.tenant_id)},
        )
        result = await db.execute(text(validated_sql))
        return result.fetchall()
```

### 2.2 Synapse API 호출의 tenant_id 격리

Oracle은 Neo4j에 직접 접근하지 않고 Synapse API를 경유한다. 모든 호출에 `X-Tenant-Id` 헤더를 포함해야 한다.

```http
GET /api/v1/graph/search?case_id=... HTTP/1.1
Authorization: Bearer <service_token>
X-Tenant-Id: <tenant_id>
```

### 2.3 서비스 간 호출

Oracle이 Synapse의 그래프를 조회할 때는 Service Token을 사용하며, tenant_id를 요청 헤더에 포함한다.

```python
# Oracle → Synapse 호출 시 tenant_id 전달
headers = {
    "Authorization": f"Bearer {SERVICE_TOKEN_ORACLE}",
    "X-Tenant-Id": str(user.tenant_id),
}
response = await synapse_client.get(
    f"/graph/search?case_id={case_id}",
    headers=headers,
)
```

---

## 3. 감사 로깅

sql-safety.md §4의 감사 로깅 정책을 따른다. 추가로 접근 제어 관련 이벤트를 기록한다.

```python
# 접근 거부 감사 로그
logger.warning(
    "audit_access_denied",
    user_id=str(user.user_id),
    tenant_id=str(user.tenant_id),
    role=user.role,
    endpoint=request.url.path,
    required_permission=required_permission,
)
```

---

## 금지 사항 (Forbidden)

- tenant_id 필터 없이 대상 DB에 쿼리 실행
- tenant_id 없이 Synapse API 호출
- SQL에 tenant_id를 f-string으로 조합 (파라미터 바인딩만 사용)
- 사용자 입력에서 tenant_id를 받기 (JWT에서만 추출)

## 필수 사항 (Required)

- 모든 Oracle API에 JWT 검증 적용
- 모든 NL2SQL 실행에 DB 세션 GUC `app.current_tenant_id` 설정
- 모든 Synapse API 호출에 `X-Tenant-Id` 헤더 포함
- 접근 거부 시 감사 로그 기록

## 관련 문서

- [sql-safety.md](sql-safety.md): SQL 3중 방어 정책
- Core auth-model.md: JWT 인증 모델, 시스템 역할 SSOT
- Core data-isolation.md: 4중 격리 모델
