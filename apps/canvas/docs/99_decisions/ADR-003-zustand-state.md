# ADR-003: Zustand 상태 관리 선택

## 상태

Accepted (수락됨)

## 배경

K-AIR에서는 Pinia(Vue의 공식 상태 관리)를 사용했다. React로 전환하면서 클라이언트 상태 관리 라이브러리를 선택해야 했다. 특히, K-AIR에서 Pinia store에 서버 데이터와 UI 상태가 혼재되어 캐시 무효화가 복잡했던 문제를 해결해야 했다.

### 요구사항

1. 간결한 API (보일러플레이트 최소화)
2. TypeScript 타입 안전성
3. React 외부에서 접근 가능 (WebSocket 핸들러, API 인터셉터)
4. 셀렉터 기반 구독 최적화
5. DevTools 지원
6. 미들웨어 (persist, immer)

## 고려한 옵션

### 옵션 1: Redux Toolkit (RTK)

- 업계 표준, 풍부한 생태계
- Redux DevTools 최고 수준
- 보일러플레이트 많음 (RTK로 줄였지만 여전히)
- RTK Query로 서버 상태도 관리 가능
- 러닝 커브: 중간

### 옵션 2: Zustand

- 최소한의 API (`create` 함수 하나)
- React 외부 접근 가능 (`store.getState()`, `store.subscribe()`)
- 셀렉터 기반 구독 (리렌더 최적화)
- 미들웨어: persist, immer, devtools
- 러닝 커브: 낮음

### 옵션 3: Jotai

- 원자적(atomic) 상태 모델
- React 외부 접근 제한
- Bottom-up 방식 (작은 단위 -> 조합)
- 러닝 커브: 중간

### 옵션 4: React Context + useReducer

- 추가 라이브러리 불필요
- Context 값 변경 시 하위 전체 리렌더 (최적화 어려움)
- 대규모 앱에서 성능 병목

## 선택한 결정

**옵션 2: Zustand** (클라이언트 상태 전용, 서버 상태는 TanStack Query와 분리)

## 근거

| 기준 | Redux Toolkit | Zustand | Jotai | Context | 비중 |
|------|-------------|---------|-------|---------|------|
| **API 간결성** | 중간 | 최고 | 높음 | 높음 | 25% |
| **React 외부 접근** | 가능 | 최고 | 제한 | 불가 | 25% |
| **셀렉터 최적화** | 가능 | 네이티브 | 네이티브 | 수동 | 20% |
| **TypeScript** | 높음 | 높음 | 높음 | 기본 | 15% |
| **번들 크기** | ~13KB | ~1KB | ~2KB | 0KB | 15% |

### 핵심 결정 요인

1. **React 외부 접근**: WebSocket 메시지 핸들러, Axios 인터셉터에서 `useAuthStore.getState()` 호출 필수. Jotai/Context는 이 패턴 불가
2. **K-AIR Pinia와의 유사성**: Pinia와 Zustand 모두 "단순한 store" 철학. 전환 시 사고 모델 변경 최소
3. **서버 상태 분리 강제**: Zustand는 의도적으로 데이터 페칭 기능을 제공하지 않음 -> TanStack Query와의 역할 분리가 자연스러움
4. **번들 크기**: ~1KB로 Redux의 1/13

## 부정적 결과

- Redux DevTools의 time-travel debugging 수준에 미치지 못함
- 대규모 팀에서 Zustand의 자유도가 오히려 일관성 저하 가능 (컨벤션 필요)
- RTK Query 같은 통합 데이터 페칭 없음 (TanStack Query로 별도 해결)

## 긍정적 결과

- 보일러플레이트 대폭 감소 (Redux 대비 코드량 1/3)
- WebSocket/Axios 인터셉터와의 매끄러운 통합
- 서버 상태 / 클라이언트 상태 명확한 분리 달성

## 재평가 조건

- 팀 규모 10명 이상으로 확장되어 상태 관리 일관성 문제 발생 시 Redux Toolkit 검토
- Zustand 프로젝트 유지보수 중단 시

---

## 변경 이력

| 날짜 | 작성자 | 내용 |
|------|--------|------|
| 2026-02-19 | Axiom Team | 초기 작성 |
