# Backend-for-Frontend (BFF) 계층

<!-- affects: frontend, api, backend -->
<!-- requires-update: 01_architecture/api-integration.md -->

## 이 문서가 답하는 질문

- Canvas에 BFF 계층이 필요한가?
- 현재 아키텍처에서 BFF 없이 어떻게 동작하는가?
- BFF 도입이 필요해지는 조건은 무엇인가?

---

## 1. 현재 상태: BFF 없음

### 1.1 결정 배경

Canvas는 현재 **BFF 계층 없이** 5개 백엔드 서비스에 직접 연결한다.

```
┌──────────────┐
│  Canvas SPA  │
└──┬──┬──┬──┬──┘
   │  │  │  │
   ▼  ▼  ▼  ▼
  Core Vision Oracle Synapse Weaver
  (직접 연결, API Gateway 없음)
```

### 1.2 BFF 없이 가능한 이유

| 조건 | 현재 상태 |
|------|-----------|
| 서비스별 API가 Canvas 요구에 맞는가? | YES - Axiom 백엔드가 Canvas 전용으로 설계됨 |
| 한 화면에 3개 이상 서비스 호출이 필요한가? | NO - 대부분 1-2개 서비스 호출 |
| 인증/인가 로직이 프론트엔드에 과도한가? | NO - JWT 토큰 자동 첨부로 충분 |
| 응답 데이터 변환이 복잡한가? | NO - 서비스 응답이 UI에 적합 |

### 1.3 K-AIR와의 차이

K-AIR는 Spring Boot API Gateway(`process-gpt-gs-main/gateway`)를 사용했다.

```
K-AIR:   Vue SPA -> Gateway (Spring Boot) -> 각 서비스
Canvas:  React SPA ────────────────────────→ 각 서비스
```

K-AIR에서 Gateway가 필요했던 이유:
- Keycloak JWT 검증을 Gateway에서 수행
- X-Forwarded-Host 기반 멀티테넌트 라우팅
- 서비스 디스커버리 (Kubernetes 내부)

Canvas에서 불필요한 이유:
- 인증은 Axios 인터셉터에서 처리
- 테넌트 ID는 X-Tenant-Id 헤더로 직접 전달
- 서비스 URL은 환경 변수로 확정

---

## 2. BFF 도입 기준

### 2.1 도입 트리거 조건

다음 조건 중 **2개 이상** 충족 시 BFF 도입을 검토한다:

| # | 조건 | 현재 | 임계값 |
|---|------|------|--------|
| 1 | 한 화면에서 3개 이상 서비스 동시 호출 필요 | 최대 2개 | 5개 이상 화면 |
| 2 | 응답 데이터 조합/변환 로직이 프론트엔드에 과도 | 단순 매핑 | 3개 이상 화면에서 복잡한 변환 |
| 3 | 인증/인가 요구사항 복잡화 | JWT 자동 첨부 | ABAC, 필드 레벨 권한 |
| 4 | 프론트엔드 빌드 크기 과도 | (미측정) | 500KB+ gzip |
| 5 | 모바일/데스크톱 등 멀티 클라이언트 | 웹만 | 2개 이상 클라이언트 |

### 2.2 BFF 도입 시 구조

```
┌──────────────┐     ┌───────────────┐
│  Canvas SPA  │────→│  BFF (Node.js) │
└──────────────┘     └──┬──┬──┬──┬───┘
                        │  │  │  │
                        ▼  ▼  ▼  ▼
                    Core Vision Oracle Synapse Weaver
```

BFF 기술 스택 후보: Node.js + Fastify (TypeScript 공유), Hono (경량)

---

## 결정 사항 (Decisions)

- 현 시점에서 BFF 불필요, 직접 서비스 호출
  - 근거: 1.2 섹션의 조건 모두 충족
  - 재평가 조건: 2.1 섹션의 트리거 조건 참조

## 사실 (Facts)

- K-AIR는 Spring Boot Gateway 사용 (Canvas에서는 제거)
- Canvas는 5개 서비스에 Axios 직접 연결

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 (BFF 불필요 결정 기록) |
