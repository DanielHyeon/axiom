# Feature 완료 정의 (Definition of Done)

> **적용 범위**: Canvas 프론트엔드 모든 Feature 구현에 적용
> **작성일**: 2026-03-24

---

## 완료 체크리스트

Feature는 아래 **모든 항목**을 충족해야 "완료(Done)" 상태로 전환할 수 있다.

### 기능 (Functional)

- [ ] UI 컴포넌트가 설계대로 렌더링된다
- [ ] 실 API와 연동되어 데이터가 올바르게 표시된다 (mock 잔존 불가)
- [ ] 에러 상태(API 실패, 네트워크 끊김)에서 적절한 에러 UI를 표시한다
- [ ] 빈 상태(Empty State)가 구현되어 있다
- [ ] 로딩 상태(Skeleton/Spinner)가 구현되어 있다
- [ ] 상태 전이(FSM)가 있는 경우, 모든 전이가 가드와 함께 동작한다

### 품질 (Quality)

- [ ] 단위 테스트: 핵심 훅/스토어/유틸에 테스트 존재
- [ ] E2E: 해당 Feature의 핵심 경로 1개 이상 Playwright 시나리오 존재
- [ ] TypeScript strict 모드에서 `any` 타입 없이 빌드 통과
- [ ] ESLint `no-hardcoded-color` 규칙 통과 (하드코딩 색상 0건)

### 접근성 (Accessibility)

- [ ] axe-core 자동 스캔 Critical/Serious 0건
- [ ] 키보드 탐색으로 모든 인터랙션 가능
- [ ] 적절한 ARIA 속성 (role, aria-label, aria-describedby 등)
- [ ] 포커스 관리: 모달 열림 시 focus trap, 닫힘 시 focus 복원

### 국제화 (i18n)

- [ ] 모든 사용자 노출 문자열이 i18n key 기반 (하드코딩 한글/영어 0건)
- [ ] ko.json / en.json 키 동기화

### 디자인 (Design)

- [ ] 다크 모드에서 정상 표시 (하드코딩 색상 없음, 디자인 토큰만 사용)
- [ ] 반응형: 최소 1024px에서 레이아웃 깨짐 없음
- [ ] PageShell 래퍼 사용 (페이지 수준 컴포넌트)

### 보안 (Security)

- [ ] 권한 가드: 해당 라우트에 RoleGuard 적용
- [ ] 버튼/액션에 usePermission 가드 적용
- [ ] X-Tenant-Id 헤더가 모든 API 호출에 포함됨

### 문서 (Documentation)

- [ ] API 계약표 (`api-contract-table.md`) 갱신
- [ ] 상태 taxonomy (`gap-analysis-v2.md` §4.1) 갱신
