# DB 연결 보안

<!-- affects: backend, operations -->
<!-- requires-update: 03_backend/service-structure.md, 08_operations/deployment.md -->

## 이 문서가 답하는 질문

- DB 연결 비밀번호는 어떻게 암호화되는가?
- 비밀번호는 어디에 저장되고, 어디에 저장되지 않는가?
- MindsDB와 Neo4j에 대한 인증은 어떻게 하는가?
- K-AIR의 보안 기술 부채를 어떻게 해결하는가?

---

## 1. K-AIR 보안 기술 부채

K-AIR 소스 분석에서 발견된 보안 문제와 Weaver의 해결 방안:

| K-AIR 문제 | 위험도 | Weaver 해결 |
|-----------|--------|------------|
| Neo4j에 비밀번호 평문 저장 | **높음** | Neo4j에 비밀번호 미저장 |
| `CORS allow_origins=["*"]` | **중간** | 특정 도메인만 허용 |
| MindsDB 인증 미설정 | **중간** | 프로덕션 인증 설정 필수 |
| SSL 미사용 | **중간** | 프로덕션 SSL 필수 |

---

## 2. 비밀번호 관리 정책

### 2.1 저장 위치

| 저장소 | 비밀번호 저장 | 형식 |
|--------|-------------|------|
| MindsDB | 저장됨 (내부) | MindsDB가 자체 관리 (변경 불가) |
| Neo4j 그래프 | **저장하지 않음** | password 필드 자체가 없음 |
| 환경 변수 | 암호화된 형태 | Vault 또는 K8s Secret |
| 로그 | **출력하지 않음** | 로깅 필터 적용 |
| API 응답 | **반환하지 않음** | Pydantic exclude 설정 |

### 2.2 비밀번호 흐름

```
사용자가 데이터소스 생성 요청
  { "password": "plain_text" }
         │
         ▼
Weaver API (입력 수신)
         │
    ┌────┴────────────────────────┐
    │                             │
    ▼                             ▼
MindsDB에 전달               API 응답에서 제외
(CREATE DATABASE              { "connection": {
 PARAMETERS = {                    "host": "...",
   "password": "..."               "user": "..."
 })                                // password 없음
                                }
MindsDB가 내부적으로          }
비밀번호 저장/관리
```

### 2.3 비밀번호 필터링

```python
# app/schemas/datasource.py

class DataSourceResponse(BaseModel):
    """API response model - password is always excluded"""
    name: str
    engine: str
    connection: dict  # password removed
    description: Optional[str]
    status: str

    @validator("connection", pre=True)
    def remove_password(cls, v):
        """Ensure password never appears in response"""
        if isinstance(v, dict):
            return {k: val for k, val in v.items() if k != "password"}
        return v
```

### 2.4 로깅 필터

```python
# app/core/logging.py

import logging
import re


class PasswordFilter(logging.Filter):
    """Filter passwords from log messages"""

    PATTERNS = [
        re.compile(r'password["\s]*[:=]["\s]*[^\s,}"]+', re.IGNORECASE),
        re.compile(r'pwd["\s]*[:=]["\s]*[^\s,}"]+', re.IGNORECASE),
    ]

    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern in self.PATTERNS:
                record.msg = pattern.sub("password=***REDACTED***", record.msg)
        return True
```

---

## 3. MindsDB 인증

### 3.1 개발 환경

```yaml
# docker-compose.yml
mindsdb:
  image: mindsdb/mindsdb:latest
  ports:
    - "47334:47334"
  # No authentication (development only)
```

### 3.2 프로덕션 환경

```yaml
# MindsDB config
mindsdb:
  api:
    http:
      host: "0.0.0.0"
      port: 47334
    auth:
      enabled: true
      username: "${MINDSDB_USER}"
      password: "${MINDSDB_PASSWORD}"
```

```python
# Weaver MindsDB client with auth
class MindsDBClient:
    def __init__(self, base_url, timeout, username=None, password=None):
        self.auth = (username, password) if username else None

    @property
    def client(self):
        kwargs = {
            "base_url": self.base_url,
            "timeout": httpx.Timeout(self.timeout),
        }
        if self.auth:
            kwargs["auth"] = self.auth
        return httpx.AsyncClient(**kwargs)
```

---

## 4. Neo4j 인증

```python
# app/config.py
class Settings(BaseSettings):
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str  # Required, no default

    # Production: use bolt+s:// for encrypted connection
    # NEO4J_URI: str = "bolt+s://neo4j.internal:7687"
```

### 프로덕션 체크리스트

| 항목 | 설명 |
|------|------|
| `bolt+s://` 프로토콜 | TLS 암호화 연결 |
| 전용 Neo4j 사용자 | `neo4j` 기본 사용자 미사용 |
| 최소 권한 | 읽기/쓰기 권한만 부여 (관리 권한 불필요) |
| 비밀번호 Vault | K8s Secret 또는 HashiCorp Vault |

---

## 5. 대상 DB 연결 보안

### 5.1 어댑터 연결 시 보안

| 항목 | 정책 |
|------|------|
| SSL 연결 | 프로덕션에서 `sslmode=require` 이상 |
| 연결 풀 크기 | 최대 5 (인트로스펙션 시) |
| 연결 타임아웃 | 30초 |
| 커넥션 수명 | 인트로스펙션 완료 후 즉시 해제 |
| 읽기 전용 사용자 | `SELECT` 권한만 부여 |

### 5.2 금지사항

```
금지:
  - 대상 DB에 DDL 실행 (CREATE, ALTER, DROP)
  - 대상 DB에 DML 실행 (INSERT, UPDATE, DELETE)
  - 대상 DB 관리자 계정 사용
  - 인트로스펙션 완료 후 연결 유지

필수:
  - 읽기 전용 사용자로 연결
  - 인트로스펙션 완료 후 풀 해제
  - 연결 정보를 에러 메시지에 포함하지 않음
```

---

## 6. CORS 정책

```python
# Production CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.axiom.kr",
        "https://canvas.axiom.kr",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### 금지사항

- `allow_origins=["*"]`는 **개발 환경에서도 사용하지 않는다**
- 명시적으로 허용된 도메인만 CORS 허용

---

## 7. API 인증/인가

Weaver API는 Axiom Core의 JWT 인증 미들웨어를 사용한다.

```python
# JWT verification (from Axiom Core)
from axiom_core.security import require_auth, require_role

@router.post("/datasources")
@require_role("admin")  # Only admins can create datasources
async def create_datasource(
    body: DataSourceCreate,
    current_user: User = Depends(require_auth),
):
    ...

@router.get("/datasources")
async def list_datasources(
    current_user: User = Depends(require_auth),  # Any authenticated user
):
    ...
```

---

## 8. 감사 로깅

모든 데이터소스 관리 작업과 쿼리 실행은 감사 로그에 기록한다.

```python
# Audit log entry
{
    "timestamp": "2026-02-19T10:00:00Z",
    "user": "admin@axiom.kr",
    "action": "datasource.create",
    "target": "erp_db",
    "details": {
        "engine": "postgresql",
        "host": "erp-db.internal"
    },
    "ip": "10.0.1.100",
    "result": "success"
}
```

| 기록 항목 | 포함 | 미포함 |
|-----------|------|--------|
| 사용자 ID | O | - |
| 작업 유형 | O | - |
| 대상 리소스 | O | - |
| 호스트/포트 | O | - |
| 비밀번호 | - | O (절대 미포함) |
| 쿼리 SQL | O (처음 200자) | 전체 SQL |
| IP 주소 | O | - |

---

## 9. 관련 문서

| 문서 | 설명 |
|------|------|
| `03_backend/service-structure.md` | 보안 설정 모듈 |
| `06_data/datasource-config.md` | 엔진별 연결 설정 |
| `08_operations/deployment.md` | 프로덕션 보안 설정 |
| `01_architecture/metadata-service.md` | 메타데이터 서비스 아키텍처 (테넌트 격리) |
| `(Core) 06_data/database-operations.md` | DB 커넥션 풀, 백업/복구, DR 전략 |
