# E2E 핵심 여정 정의 (Core Journey Specification)

<!-- affects: frontend, qa -->
<!-- requires-update: 04_frontend-implementation-plan.md -->

## 이 문서가 답하는 질문

- Canvas 애플리케이션의 가장 핵심적인 사용자 여정(통합 E2E 시나리오)은 무엇인가?
- 이 시나리오를 통해 검증하고자 하는 서비스의 핵심 가치 흐름은 어떻게 구성되는가?
- 추후 Playwright 등 자동화 E2E 테스트에서 기준점이 되는 체크포인트는 무엇인가?

---

## 1. 핵심 가치 흐름 (Core Value Loop)

Canvas의 MVP(P0/P1)가 고객에게 제공하는 최우선 가치는 **"데이터 모니터링 → 이상 징후 케이스 파악 → AI 보조 문서 작성(HITL) → 의사결정 기록 및 후속 분석"**의 일원화된 파이프라인 경험입니다. 이 여정이 단절 없이(Seamless) 동작하는지 검증하는 것이 가장 중요합니다.

### 시나리오 대상 역할 (Role)
* **주 수행자(Actor)**: `attorney` (혹은 도메인 분석/작업자)
* **보조 수행자(Reviewer)**: `manager` (승인권자)

---

## 2. E2E 시나리오 단계별 명세

### Step 1: 인증 및 진입 (Authentication & Entry)
1. 사용자가 `/login` 페이지에 접속한다.
2. `attorney` 계정 자격 증명(ex: `test-attorney@axiom.ai`, `password`)을 입력하고 로그인한다.
3. `/` (케이스 대시보드) 경로로 올바르게 리다이렉트 된다.
4. **[검증 포인트]**
   - 브라우저 스토리지에 `accessToken`과 `refreshToken`이 정상 발급/저장됨.
   - 대시보드 화면에 해당 역할 전용 패널(MyWorkitemsPanel 등)이 렌더링됨.
   - "안녕하세요, OOO님" RoleGreeting 컴포넌트가 올바르게 표시됨.

### Step 2: 대시보드 및 케이스 확인 (Dashboard Monitoring)
1. 사용자가 내 할당 업무 패널(MyWorkitems)에서 "진행중" 또는 "TODO" 상태의 식별된 케이스("물류최적화 - 현황 분석") 카드를 클릭한다.
2. `/cases/:id` 경로로 진입하여 케이스 상세 현황을 파악한다.
3. 문서 산출물을 작성/조회하기 위해 문서 목록(`/documents`) 메뉴로 이동한다.
4. **[검증 포인트]**
   - 케이스 클릭 시 네트워크 로딩(Suspense)이 정상적으로 Fallback을 거쳐 데이터를 표시함.

### Step 3: AI 문서 생성 및 편집 (Document Management & HITL)
1. 문서 목록에서 "Generate New" 버튼을 눌러 AI 초안 생성 워크플로우를 트리거한다.
2. (Mock) AI가 제공한 초기 작성 문서(Markdown) 내용이 에디터 영역에 노출된다. (`/documents/:id` 에디터 페이지)
3. 사용자가 Monaco Editor에서 AI 초안 내용 중 일부 텍스트를 수정하여 보완(Human-in-the-Loop)한다.
4. 사용자가 우측 상단의 "Request Review(리뷰 요청)" 버튼을 클릭하여 리뷰 사이클로 넘긴다.
5. **[검증 포인트]**
   - 문서 생성 과정에서 Core API/Vision API (혹은 Mock) 통신을 거쳐 반환된 데이터 포맷(Document)이 정상 UI 렌더링됨.
   - 수정 사항이 낙관적 업데이트(Optimistic Update)로 로컬 상태 캐시(Query)에 바로 반영됨.

### Step 4: 매니저 승인 (Manager Approval) - *선택 모델링*
1. (자동화 스크립트를 통해 `manager` 탭으로 전환 또는 상태 모킹)
2. `manager`가 ApprovalQueuePanel에서 대기 중인 문서를 누른다.
3. 원본(AI) 대 수정본(attorney) Diff 뷰를 확인한 뒤 "Approve(승인)"을 클릭한다.
4. **[검증 포인트]**
   - HITL 워크플로우 상태가 `draft` → `in_review` → `approved`로 전이됨을 확인.

### Step 5: 자연어 기반 후속 분석 (NL2SQL Chat)
1. 사용자가 좌측 사이드바 또는 QuickActions 패널을 통해 "NL2SQL Chat (`/nl2sql`)"으로 이동한다.
2. 채팅 입력창에 "이번 승인된 분석 내용을 바탕으로 관련된 작년도 물류 통계 내역을 뽑아줘" 라고 자연어로 입력 후 전송한다.
3. SSE(Server-Sent Events) 스트리밍을 통해 AI 응답(생성된 SQL 및 메시지)이 타이핑 이펙트와 함께 UI에 표시된다.
4. 생성된 SQL이 뷰어(Data Grid/Table) 컴포넌트에 결괏값을 렌더링한다.
5. **[검증 포인트]**
   - 이전 컨텍스트 유지 기능(채팅 내역)이 동작하고, 백엔드의 SSE 스트림 이벤트가 프론트엔드에 끊김 없이 수용되는지 확인.

---

## 3. 예외 및 실패 대응 시나리오 (Graceful Degradation)

E2E 핵심 여정에서 반드시 포함되어야 할 오류 검증 시나리오입니다.

1. **토큰 만료 방어**: 세션 15분 만료를 강제로 재현(수동 변조) 시, Axios Response Interceptor가 401을 포착하고 `refreshAccessToken` 연산 후 원래 요청을 재실행하여 사용자 경험이 단절되지 않아야 함.
2. **API 타임아웃/오류 처리**: 서비스군 중 `Oracle API`(NL2SQL 담당)가 다운된 상태(강제 500 에러 모재현)일 때, 앱 전체가 크래시되지 않고 ErrorBoundary가 동작하여 해당 영역에만 에러 fallback UI를 표시해야 함.

---

## 4. 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.0 | Axiom Team | E2E 핵심 여정 정의 초기 작성 (CAN-S1-005) |
