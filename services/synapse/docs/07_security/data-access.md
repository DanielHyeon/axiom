# 그래프 접근 제어 및 케이스별 격리

## 이 문서가 답하는 질문

- 온톨로지 데이터에 대한 접근 제어는 어떻게 구현하는가?
- 케이스별 데이터 격리는 어떻게 보장하는가?
- 서비스 간 호출의 인증/인가는?
- 민감 데이터 보호 정책은?

<!-- affects: api, backend -->
<!-- requires-update: 02_api/* -->

---

## 1. 접근 제어 모델

### 1.1 인증 (Authentication)

| 호출 유형 | 인증 방식 | 토큰 발행자 |
|----------|----------|-----------|
| Canvas → Core → Synapse | JWT Bearer Token | Core 인증 서비스 |
| Oracle → Synapse | Service Token | Core 서비스 레지스트리 |
| Core → Synapse (이벤트) | Redis Streams ACL | 인프라 레벨 |

### 1.2 인가 (Authorization)

#### 역할 기반 접근 제어 (RBAC)

Synapse는 모듈별 역할 이름을 사용한다. Core 시스템 역할에서 파생된다 (Core auth-model.md §5.3 참조).

| Synapse 역할 | Core 시스템 역할 원천 | 설명 | 온톨로지 권한 |
|-------------|---------------------|------|-------------|
| `admin` | admin | 시스템 관리자 | 전체 CRUD + 삭제 + 배치 작업 |
| `case_editor` | manager, attorney + 케이스 trustee | 프로젝트 편집자 | 소속 케이스 CRUD |
| `case_viewer` | analyst, staff, viewer + 케이스 viewer | 프로젝트 열람자 | 소속 케이스 읽기 전용 |
| `hitl_reviewer` | 케이스 reviewer | HITL 검토자 | 추출 결과 검토/승인/거부 |
| `schema_editor` | engineer | 스키마 편집자 | 테이블/컬럼 설명 편집 |
| `schema_viewer` | (모든 인증된 사용자) | 스키마 열람자 | 테이블/컬럼 정보 읽기 |

#### 권한 매트릭스

| 엔드포인트 그룹 | admin | case_editor | case_viewer | hitl_reviewer | schema_editor |
|---------------|-------|------------|------------|--------------|--------------|
| 온톨로지 조회 | O | O | O | O | - |
| 온톨로지 생성/수정 | O | O | - | - | - |
| 온톨로지 삭제 | O | - | - | - | - |
| 추출 작업 시작 | O | O | - | - | - |
| 추출 결과 조회 | O | O | O | O | - |
| HITL 검토 | O | - | - | O | - |
| 스키마 편집 | O | - | - | - | O |
| 스키마 조회 | O | O | O | - | O |
| 그래프 검색 | O | O | O | - | O |
| 배치 임베딩 | O | - | - | - | - |
| 그래프 통계 | O | - | - | - | - |

---

## 2. 케이스별 데이터 격리

### 2.1 격리 원칙

비즈니스 프로세스 데이터는 조직별로 민감한 정보를 포함하므로, 프로젝트 간 데이터 격리는 보안의 핵심이다.

**핵심 규칙**: 모든 Neo4j 쿼리에 반드시 `case_id` 필터를 포함한다.

### 2.2 Neo4j 레벨 격리

```cypher
// CORRECT: always filter by case_id
MATCH (r:Resource {case_id: $case_id})
RETURN r

// FORBIDDEN: querying without case_id filter
MATCH (r:Resource)
RETURN r
// This query is NEVER allowed in production code
```

### 2.3 API 레벨 격리

```python
# app/dependencies.py
from fastapi import Depends, HTTPException

async def verify_case_access(
    case_id: str,
    current_user: User = Depends(get_current_user)
) -> str:
    """
    Verify that the current user has access to the specified case.
    This dependency MUST be used on all case-scoped endpoints.
    """
    if not await has_case_access(current_user.id, case_id, current_user.tenant_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "ACCESS_DENIED", "message": "No access to this case"}
        )
    return case_id
```

```python
# Usage in API endpoint
@router.get("/cases/{case_id}/ontology")
async def get_case_ontology(
    case_id: str = Depends(verify_case_access),  # Access check
    service: OntologyService = Depends(get_ontology_service),
):
    return await service.get_case_ontology(case_id)
```

### 2.4 서비스 레벨 격리

```python
# app/graph/ontology_schema.py
class OntologySchemaManager:
    async def get_nodes(self, case_id: str, layer: str) -> list:
        """
        All graph queries MUST include case_id.
        This is enforced at the graph layer.
        """
        if not case_id:
            raise ValueError("case_id is required for all graph queries")

        query = """
        MATCH (n {case_id: $case_id})
        WHERE n:Resource OR n:Process OR n:Measure OR n:KPI
        RETURN n
        """
        # case_id is always parameterized, never concatenated
        async with self.neo4j.session() as session:
            result = await session.run(query, case_id=case_id)
            return [record async for record in result]
```

### 2.5 tenant_id 격리 (멀티테넌트)

case_id에 더하여 tenant_id로 테넌트 간 격리를 보장한다. Core의 4중 격리 모델 중 Layer 4(명시적 WHERE 조건)에 해당한다.

> **용어 통일**: Core SSOT 기준으로 `tenant_id`를 사용한다 (이전 문서의 `org_id`와 동일).

```cypher
// Tenant-level isolation (모든 Neo4j 쿼리에 필수)
MATCH (n {tenant_id: $tenant_id, case_id: $case_id})
RETURN n
```

---

## 3. 서비스 간 인증

### 3.1 Service Token

Oracle, Vision 등 다른 Axiom 서비스가 Synapse를 호출할 때는 Service Token을 사용한다.

```python
import hmac
from fastapi import Header, HTTPException

# Service-to-service authentication
# 토큰은 환경변수에서 로드 (하드코딩 금지)
SERVICE_TOKENS = {
    "oracle": os.environ["SERVICE_TOKEN_ORACLE"],
    "vision": os.environ["SERVICE_TOKEN_VISION"],
    "core": os.environ["SERVICE_TOKEN_CORE"],
}

async def verify_service_token(
    authorization: str = Header(),
) -> ServiceIdentity:
    token = authorization.replace("Bearer ", "")
    for service_name, expected_token in SERVICE_TOKENS.items():
        # hmac.compare_digest: 타이밍 공격 방지 (== 비교 금지)
        if hmac.compare_digest(token, expected_token):
            return ServiceIdentity(name=service_name)
    raise HTTPException(status_code=401, detail="Invalid service token")
```

### 3.2 서비스별 접근 범위

| 서비스 | 접근 가능 API | 제약 |
|--------|-------------|------|
| Oracle | `/graph/search`, `/graph/vector-search`, `/graph/fk-path` | 읽기 전용 |
| Vision | `/ontology-path` | 읽기 전용 |
| Core | 모든 API | case_id 범위 |

---

## 4. 민감 데이터 보호

### 4.1 민감 데이터 분류

| 데이터 | 민감도 | 보호 방법 |
|--------|-------|----------|
| 인명 (담당자, 이해관계자) | 높음 | 로그에서 마스킹, 검색 시 익명화 옵션 |
| 금액 | 중 | 접근 제어로 보호 |
| 의사결정 내용 | 높음 | 접근 제어 + 감사 로깅 |
| 회사 재무 정보 | 높음 | 접근 제어 + 감사 로깅 |
| 온톨로지 구조 | 낮음 | 일반 접근 제어 |

### 4.2 감사 로깅

온톨로지 데이터의 생성/수정/삭제/조회에 대해 감사 로그를 남긴다.

```python
# Audit log entry
{
    "timestamp": "2024-06-16T10:00:00Z",
    "action": "ontology.node.create",
    "user_id": "user-uuid",
    "case_id": "case-uuid",
    "node_id": "node-uuid",
    "node_type": "Company:Resource",
    "ip_address": "10.0.1.15",
    "user_agent": "Axiom Canvas/1.0"
}
```

### 4.3 LLM 데이터 보호

GPT-4o에 전송되는 텍스트에서 민감 정보를 처리하는 전략:

| 전략 | 설명 | 적용 |
|------|------|------|
| 처리 동의 | 사용자가 LLM 처리에 동의 | 추출 작업 시작 시 확인 |
| 최소 전송 | 청킹된 텍스트만 전송 (전체 문서 아님) | 기본 적용 |
| 결과 저장 | LLM 응답은 Synapse 내부에만 저장 | 기본 적용 |
| 데이터 보존 | OpenAI API 데이터 보존 정책 확인 | 계약 검토 필요 |

---

## 5. 보안 체크리스트

- [ ] 모든 API 엔드포인트에 인증 미들웨어 적용
- [ ] 모든 case-scoped API에 case_id 접근 검증
- [ ] 모든 Neo4j 쿼리에 case_id 파라미터 포함
- [ ] case_id를 문자열 연결이 아닌 파라미터 바인딩으로 전달
- [ ] 민감 데이터 로깅 마스킹
- [ ] 감사 로그 활성화
- [ ] Service Token 환경변수 관리 (하드코딩 금지)
- [ ] LLM 데이터 전송 동의 절차

---

## 금지 규칙

- case_id 없이 온톨로지 쿼리를 실행하지 않는다
- case_id를 Cypher 문자열에 직접 연결하지 않는다 (파라미터 바인딩만 사용)
- 민감 데이터 (인명, 금액)를 로그에 평문으로 기록하지 않는다
- Service Token을 소스코드에 하드코딩하지 않는다

## 필수 규칙

- 모든 데이터 변경에 감사 로그를 남긴다
- 서비스 간 호출은 Service Token으로 인증한다
- 사용자 요청은 JWT + RBAC로 인가한다

---

## 근거 문서

- K-AIR 역설계 분석 보고서 섹션 4.11.5 (모듈 간 통신 금지 패턴)
- `01_architecture/architecture-overview.md` (서비스 경계)
