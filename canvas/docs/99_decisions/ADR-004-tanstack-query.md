# ADR-004: TanStack Query 데이터 페칭 선택

## 상태

Accepted (수락됨)

## 배경

ADR-003에서 Zustand를 클라이언트 상태 관리로 선택했다. 서버 상태(API에서 오는 데이터)를 관리할 별도 솔루션이 필요했다. K-AIR에서는 Pinia store 안에서 `loading`, `error`, `data`를 모두 관리하며 서버 데이터와 UI 상태가 혼재되는 문제가 있었다.

### K-AIR의 문제

```javascript
// K-AIR Pinia store (문제 패턴)
export const useDatasourcesStore = defineStore('datasources', () => {
  const datasources = ref([]);       // 서버 데이터
  const loading = ref(false);        // 로딩 상태
  const error = ref(null);           // 에러 상태
  const selectedFilter = ref('all'); // UI 상태 <- 혼재!

  async function fetchDatasources() {
    loading.value = true;
    try {
      datasources.value = await api.getAll();
    } catch (e) {
      error.value = e;
    } finally {
      loading.value = false;
    }
  }
  // 캐싱 없음, 중복 요청 방지 없음, 재시도 없음, stale 판단 없음
});
```

## 고려한 옵션

### 옵션 1: Zustand에서 서버 상태도 관리

- 추가 라이브러리 불필요
- 수동으로 캐싱, 재시도, 무효화 구현 필요
- K-AIR와 같은 문제 반복 우려

### 옵션 2: RTK Query (Redux Toolkit Query)

- Redux 생태계 통합
- 자동 캐싱, 태그 기반 무효화
- Redux 전체를 도입해야 함 (ADR-003과 충돌)

### 옵션 3: TanStack Query (React Query)

- Zustand와 독립적으로 동작
- 자동 캐싱, 재시도, 무효화, 프리페칭
- 낙관적 업데이트 패턴 내장
- DevTools 제공
- 라이브러리 독립적 (React, Vue, Solid 등)

### 옵션 4: SWR (Vercel)

- 간결한 API
- stale-while-revalidate 패턴
- TanStack Query 대비 기능 제한 (mutation, 무효화)
- Vercel 종속성

## 선택한 결정

**옵션 3: TanStack Query v5**

## 근거

| 기준 | Zustand 내장 | RTK Query | TanStack Query | SWR | 비중 |
|------|------------|-----------|---------------|-----|------|
| **캐싱/무효화** | 수동 | 자동 (태그) | 자동 (키) | 자동 | 25% |
| **낙관적 업데이트** | 수동 | 지원 | 최고 | 제한 | 20% |
| **Zustand 호환** | 해당 없음 | RTK 필요 | 완전 독립 | 완전 독립 | 20% |
| **SSE/WS 연동** | 수동 | 수동 | invalidate | invalidate | 15% |
| **DevTools** | 없음 | Redux DT | 전용 DT | 없음 | 10% |
| **번들 크기** | 0 | ~13KB | ~12KB | ~4KB | 10% |

### 핵심 결정 요인

1. **Zustand와의 완전한 분리**: TanStack Query는 "서버 상태만" 관리, Zustand는 "클라이언트 상태만" 관리. 역할이 명확
2. **Query Key 기반 캐시 무효화**: WebSocket 이벤트 수신 시 `queryClient.invalidateQueries({ queryKey: [...] })`로 정확한 무효화 가능
3. **낙관적 업데이트 패턴**: 문서 승인, 알림 읽음 처리 등 UX 핵심 기능에 필수
4. **staleTime/gcTime 세분화**: 데이터 특성별 캐싱 전략 적용 가능 (온톨로지 30분 vs 알림 0초)
5. **Suspense 통합**: React 18 Suspense와 네이티브 연동

## 부정적 결과

- 추가 라이브러리 의존 (~12KB)
- Query Key 관리 복잡도 (키 팩토리 패턴 도입 필요)
- Zustand + TanStack Query 이중 학습

## 긍정적 결과

- K-AIR의 "서버 데이터 혼재" 문제 근본 해결
- 네트워크 요청 최적화 (중복 방지, 자동 재시도, 윈도우 포커스 리페치)
- 일관된 loading/error/data 패턴

## 재평가 조건

- 서버 상태 관리 요구가 단순해져 Zustand만으로 충분해질 때 (가능성 낮음)
- TanStack Query 후속 메이저 버전에서 Breaking Change가 클 때

---

## 변경 이력

| 날짜 | 작성자 | 내용 |
|------|--------|------|
| 2026-02-19 | Axiom Team | 초기 작성 |
