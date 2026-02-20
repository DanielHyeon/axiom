# 데이터 접근 제어 및 케이스 기반 격리

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **근거**: Axiom Core 보안 아키텍처, 03_backend/service-structure.md

---

## 이 문서가 답하는 질문

- Vision 모듈에서 데이터 접근 제어는 어떻게 이루어지는가?
- 멀티테넌트 환경에서 케이스 데이터 격리는 어떻게 보장하는가?
- OLAP 쿼리에서 tenant_id 기반 격리는 어떻게 적용되는가?
- 어떤 역할이 어떤 데이터에 접근 가능한가?

---

## 1. 인증 모델

### 1.1 JWT 토큰 검증

Vision은 자체 인증을 수행하지 않는다. Axiom Core가 발급한 JWT를 검증만 한다.

```python
# JWT payload structure (from Axiom Core — Core auth-model.md SSOT 참조)
{
    "sub": "user-uuid",           # User ID
    "email": "user@example.com",  # Email
    "tenant_id": "tenant-uuid",   # Tenant ID (snake_case, Core SSOT)
    "role": "manager",            # System role (단수형 문자열)
    "permissions": ["case:read", "case:write"],
    "case_roles": {               # Case-specific roles (lowercase)
        "case-uuid-1": "trustee",
        "case-uuid-2": "viewer"
    },
    "exp": 1740000000,
    "iat": 1739913600
}
```

```python
# Vision JWT dependency
async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> CurrentUser:
    """
    Validate JWT and extract user context.
    Does NOT call Core API - validates locally using shared secret.
    """
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    return CurrentUser(
        user_id=UUID(payload["sub"]),
        tenant_id=UUID(payload["tenant_id"]),
        system_role=payload["role"],          # 단수형 문자열
        case_roles=payload.get("case_roles", {}),
    )
```

### 1.2 역할 기반 접근 제어 (RBAC)

시스템 역할은 Core auth-model.md의 SSOT를 따른다 (lowercase).

| 시스템 역할 | 설명 | Vision 권한 |
|-----------|------|-----------|
| admin | 시스템 관리자 | 모든 작업 가능, 큐브 관리, ETL 트리거 |
| manager | 조직 관리자 | 시나리오 생성/수정, 분석 실행 |
| analyst | 재무/데이터 분석가 | 담당 케이스 분석 실행, OLAP 쿼리 |
| viewer | 조회자 | 결과 조회만 |

케이스 역할은 JWT `case_roles`에서 추출한다 (lowercase).

| 케이스 역할 | 설명 | Vision 권한 |
|-----------|------|-----------|
| trustee | 케이스 담당자 | 해당 케이스의 시나리오 CRUD, 분석 실행 |
| reviewer | 검토자 | 해당 케이스의 결과 조회, 승인 |
| viewer | 조회자 | 해당 케이스의 결과 조회만 |

---

## 2. 데이터 격리

### 2.1 테넌트(tenant_id) 기반 격리

모든 Vision 데이터는 `tenant_id`로 격리된다. Core의 4중 격리 모델과 동일한 GUC 변수(`app.current_tenant_id`)를 사용한다.

```python
# Middleware: Set tenant_id for RLS (Core와 동일한 GUC 변수)
@app.middleware("http")
async def set_tenant_context(request: Request, call_next):
    user = request.state.user  # From JWT
    async with get_session() as db:
        # 파라미터 바인딩 사용 (f-string SQL 조합 금지 — SQL 인젝션 방지)
        await db.execute(
            text("SET LOCAL app.current_tenant_id = :tenant_id"),
            {"tenant_id": str(user.tenant_id)},
        )
    return await call_next(request)
```

### 2.2 케이스(case_id) 기반 접근 제어

```python
async def verify_case_access(
    case_id: UUID,
    user: CurrentUser,
    required_role: str = "viewer"
) -> None:
    """
    Verify user has required role for the specific case.
    """
    # System admin can access all cases in their org
    if user.system_role == "admin":
        return

    # Check case-specific role
    case_role = user.case_roles.get(str(case_id))
    if not case_role:
        raise HTTPException(403, "No access to this case")

    role_hierarchy = {"trustee": 3, "reviewer": 2, "viewer": 1}
    if role_hierarchy.get(case_role, 0) < role_hierarchy.get(required_role, 0):
        raise HTTPException(403, f"Insufficient role: {case_role}, required: {required_role}")
```

### 2.3 RLS (Row-Level Security) 정책

Vision 소유 테이블에 RLS 적용:

```sql
-- what_if_scenarios: tenant_id 직접 보유
ALTER TABLE what_if_scenarios ENABLE ROW LEVEL SECURITY;
CREATE POLICY scenarios_tenant_isolation ON what_if_scenarios
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- case_causal_analysis: tenant_id 직접 보유
ALTER TABLE case_causal_analysis ENABLE ROW LEVEL SECURITY;
CREATE POLICY causal_analysis_tenant_isolation ON case_causal_analysis
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- cube_definitions: tenant_id 직접 보유
ALTER TABLE cube_definitions ENABLE ROW LEVEL SECURITY;
CREATE POLICY cubes_tenant_isolation ON cube_definitions
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- causal_graphs: tenant_id 직접 보유
ALTER TABLE causal_graphs ENABLE ROW LEVEL SECURITY;
CREATE POLICY causal_graphs_tenant_isolation ON causal_graphs
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- scenario_results: scenario를 통한 간접 격리
-- RLS 대신 애플리케이션 레벨에서 scenario_id 검증
-- (scenario의 tenant_id를 먼저 확인한 후 results 접근)
```

### 2.4 OLAP 쿼리 격리

Materialized View는 모든 테넌트의 데이터를 포함하므로, 쿼리 시 반드시 tenant_id 필터를 추가한다.

```python
import sqlglot
from sqlglot import exp

def add_tenant_filter_to_sql(sql: str, tenant_id: UUID) -> tuple[str, dict]:
    """
    Inject tenant_id filter into generated pivot SQL using AST 변환.
    문자열 치환이 아닌 SQL 파싱 기반으로 안전하게 주입한다.

    Returns:
        (sql_with_placeholder, params) — 파라미터 바인딩과 함께 사용
    """
    # sqlglot으로 AST 파싱 후 WHERE 조건 추가
    parsed = sqlglot.parse_one(sql, dialect="postgres")

    # tenant_id 필터를 파라미터 바인딩으로 추가
    tenant_filter = sqlglot.parse_one("tenant_id = :tenant_id", dialect="postgres")
    existing_where = parsed.find(exp.Where)

    if existing_where:
        # 기존 WHERE에 AND 조건 추가
        existing_where.this = exp.And(this=tenant_filter, expression=existing_where.this)
    else:
        # 새 WHERE 절 추가
        parsed.set("where", exp.Where(this=tenant_filter))

    return parsed.sql(dialect="postgres"), {"tenant_id": str(tenant_id)}
```

> **금지**: 문자열 치환(`.replace()`, f-string)으로 SQL에 tenant_id를 주입하지 않는다. 반드시 AST 파싱 또는 파라미터 바인딩을 사용한다.

---

## 3. API별 접근 제어 매트릭스

시스템 역할(`role`)과 케이스 역할(`case_roles`)이 조합되어 접근을 결정한다.

| API | admin | manager/analyst | 케이스 trustee | 케이스 reviewer | 케이스 viewer |
|-----|:-----:|:---------------:|:-------------:|:--------------:|:------------:|
| 시나리오 목록 조회 | O | O | O (담당) | O (담당) | O (담당) |
| 시나리오 상세 조회 | O | O | O (담당) | O (담당) | O (담당) |
| 시나리오 생성 | O | O | O (담당) | X | X |
| 시나리오 수정 | O | O | O (담당) | X | X |
| 시나리오 삭제 | O | X | X | X | X |
| 시나리오 계산 | O | O | O (담당) | X | X |
| 피벗 쿼리 | O | O | O | O | O |
| NL 질의 | O | O | O | O | O |
| 큐브 스키마 업로드 | O | X | X | X | X |
| ETL 트리거 | O | X | X | X | X |
| 근본원인 분석 실행 | O | O | O (담당) | X | X |
| 근본원인 결과 조회 | O | O | O (담당) | O (담당) | O (담당) |

---

## 4. 감사 로깅 (Audit)

모든 데이터 변경 작업은 감사 로그에 기록된다.

```python
# Audit log for sensitive operations
logger.info(
    "audit_scenario_created",
    user_id=str(user.user_id),
    tenant_id=str(user.tenant_id),
    case_id=str(case_id),
    scenario_id=str(scenario_id),
    action="CREATE",
    ip_address=request.client.host,
)

logger.info(
    "audit_etl_triggered",
    user_id=str(user.user_id),
    sync_type="full",
    target_views=["mv_business_fact"],
    action="ETL_TRIGGER",
)
```

---

## 금지 사항 (Forbidden)

- tenant_id 필터 없이 OLAP 쿼리 실행
- 케이스 역할 검증 없이 시나리오 접근
- JWT 검증 우회 (내부 서비스 간 호출에도 JWT 필수)
- RLS 비활성화 상태에서 운영

## 필수 사항 (Required)

- 모든 Vision API에 JWT 검증 적용
- 모든 케이스 관련 API에 case_role 검증 적용
- 모든 OLAP 쿼리에 tenant_id 필터 주입
- 데이터 변경 작업에 감사 로그 기록
- RLS 활성화 상태 확인 (서비스 시작 시)

<!-- affects: 02_api, 03_backend/service-structure.md -->
