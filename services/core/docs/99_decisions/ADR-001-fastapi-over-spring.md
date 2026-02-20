# ADR-001: Spring Boot 대신 FastAPI 선택

## 상태

Accepted

## 배경

K-AIR/Process-GPT 시스템은 API Gateway를 Spring Cloud Gateway (Java)로 구현하고, 백엔드 서비스를 FastAPI (Python)로 구현하는 이종(heterogeneous) 기술 스택을 사용한다. Axiom을 구축하면서 이 구조를 유지할지, 단일 기술 스택으로 통합할지 결정해야 한다.

**현재 K-AIR 구조**:
- API Gateway: Spring Boot 2.3.12 + JJWT 0.9.1 (Java)
- 백엔드 서비스: FastAPI 0.109~0.118 (Python)
- 프론트엔드: Vue 3 + Vuetify (TypeScript)

**문제**:
1. Java Gateway와 Python 서비스 간 기술 스택 분리로 인한 유지보수 복잡성
2. Gateway의 JWT 필터 로직이 Java, 서비스의 멀티테넌트 로직이 Python으로 이중 관리
3. AI/ML 생태계가 Python 중심이므로 Gateway도 Python이 효율적
4. 개발팀 규모가 작아 두 언어를 유지하기 어려움

## 검토한 옵션

### 옵션 1: Spring Boot Gateway + FastAPI 서비스 (K-AIR 현행 유지)

**장점**:
- K-AIR 코드를 그대로 이식할 수 있음
- Spring Cloud Gateway의 성숙한 라우팅/필터 기능
- Java의 안정적인 JWT 라이브러리 (JJWT)

**단점**:
- 이종 기술 스택 유지 비용 (Java + Python)
- 별도 Gateway 서비스 운영 필요
- JWT 검증 로직이 Java와 Python에 중복
- 개발자가 두 언어/프레임워크를 모두 알아야 함

### 옵션 2: FastAPI 단일 스택 (선택)

**장점**:
- Python 단일 언어로 전체 백엔드 통일
- FastAPI 미들웨어로 Gateway 기능 충분히 구현 가능
- AI/ML 생태계와 동일 언어 (LangChain, LangGraph)
- 작은 팀에서 유지보수 용이
- 별도 Gateway 서비스 불필요 (배포 복잡도 감소)

**단점**:
- K-AIR의 Java Gateway 코드를 Python으로 재작성 필요
- Spring Security의 성숙한 보안 프레임워크 대비 직접 구현 필요
- Python의 GIL 제약 (asyncio로 극복 가능)

### 옵션 3: Nginx/Kong Gateway + FastAPI

**장점**:
- 전용 Gateway의 높은 성능
- 인증 플러그인 등 풍부한 생태계

**단점**:
- 추가 인프라 서비스 운영 필요
- 커스텀 로직(멀티테넌트 라우팅) 구현이 제한적
- 팀 규모 대비 과도한 인프라 복잡도

## 선택한 결정

**옵션 2: FastAPI 단일 스택**

## 근거

1. **팀 규모**: 소규모 팀(2-3명)에서 이종 기술 스택은 유지보수 부담이 크다.
2. **AI 통합**: LangChain, LangGraph, MCP 등 AI 핵심 컴포넌트가 모두 Python이다. Gateway에서 AI 기능을 직접 호출해야 하는 경우가 많아 같은 언어가 효율적이다.
3. **성능**: FastAPI의 비동기 성능은 Spring Boot와 비교해도 충분하다 (Starlette 기반).
4. **보안**: python-jose로 JWT 검증이 가능하며, K-AIR의 JJWT 로직을 Python으로 이식하는 공수는 2일 이내이다.
5. **배포 단순화**: 별도 Gateway 서비스 없이 Core 하나로 API Gateway + 비즈니스 로직을 처리한다.

## 결과

### 긍정적 영향
- 단일 기술 스택으로 학습 비용 감소
- 배포 아티팩트 1개 감소 (Gateway 서비스 불필요)
- AI 통합 코드의 일관성 향상

### 부정적 영향
- K-AIR의 Java Gateway 코드(JWT 필터, 라우팅)를 Python으로 재작성 필요
- Spring Security의 일부 고급 기능(OAuth2 Resource Server 등)을 직접 구현해야 함

### 마이그레이션 작업
- `ForwardHostHeaderFilter.java` -> `app/core/middleware.py` (ContextVar 설정)
- `JwtAuthFilter.java` -> `app/core/security.py` (python-jose)
- `application.yml` 라우팅 규칙 -> `app/core/routes.py`
- 예상 공수: 2일

## 재평가 조건

- API 요청량이 10,000 req/sec를 초과하는 경우 -> 별도 Gateway 도입 검토
- OAuth2/OIDC 통합이 필요한 경우 -> Keycloak 또는 Auth0 도입 검토
- Core 서비스가 10개 인스턴스 이상으로 확장되는 경우 -> Service Mesh(Istio) 검토
