# TanStack Query 캐싱 전략

<!-- affects: frontend, api -->
<!-- requires-update: 01_architecture/state-management.md -->

## 이 문서가 답하는 질문

- Canvas에서 서버 데이터의 캐시 정책은 어떻게 되는가?
- 어떤 데이터를 얼마나 오래 캐시하는가?
- 캐시 무효화는 언제, 어떻게 발생하는가?
- 낙관적 업데이트는 어디에 적용하는가?

---

## 1. 캐싱 전략 총괄

### 1.1 데이터 유형별 캐시 정책

| 데이터 | Query Key | staleTime | gcTime | 전략 | 근거 |
|--------|-----------|-----------|--------|------|------|
| **케이스 목록** | `['cases', 'list', filters]` | 1분 | 10분 | 짧은 fresh + WS 무효화 | 실시간 상태 변경 빈번 |
| **케이스 상세** | `['cases', 'detail', id]` | 5분 | 30분 | 표준 | 상세 진입 후 안정적 |
| **문서 목록** | `['documents', 'list', caseId]` | 2분 | 15분 | 짧은 fresh | HITL 리뷰 상태 변경 |
| **문서 내용** | `['documents', 'detail', id]` | 5분 | 30분 | 표준 | 편집 중 자주 변경 안됨 |
| **OLAP 큐브 목록** | `['olap', 'cubes']` | 30분 | 2시간 | 긴 캐시 | 거의 변경 안됨 |
| **OLAP 쿼리 결과** | `['olap', 'query', config]` | 10분 | 1시간 | 긴 캐시 | 같은 쿼리 반복 패턴 |
| **온톨로지 그래프** | `['ontology', 'graph', params]` | 30분 | 2시간 | 매우 긴 캐시 | 구조적 데이터, 변경 드뭄 |
| **NL2SQL 히스토리** | `['nl2sql', 'history']` | 5분 | 30분 | 표준 | 대화 중 갱신 |
| **알림 목록** | `['alerts', 'feed']` | 0 (항상 stale) | 5분 | WS 주도 | WebSocket 실시간 |
| **데이터소스 목록** | `['datasources']` | 5분 | 30분 | 표준 | 변경 빈도 낮음 |
| **사용자 정보** | `['users', 'me']` | 15분 | 1시간 | 긴 캐시 | 세션 중 거의 불변 |

### 1.2 기본 설정

**구현 위치**: `apps/canvas/src/lib/queryClient.ts`  
전역 옵션 상세는 [04_frontend/query-client.md](../04_frontend/query-client.md) 참고.

- **queries**: staleTime 5분, gcTime 30분, retry 3회(지수 백오프), refetchOnWindowFocus/Reconnect/Mount true.
- **mutations**: retry 0 (필요 시 useMutation 단위로 지정).

---

## 2. 캐시 무효화 패턴

### 2.1 Mutation 후 무효화

```typescript
// 문서 상태 변경 시 관련 캐시 무효화
const approveDocument = useMutation({
  mutationFn: (docId: string) => documentApi.approve(docId),
  onSuccess: (_data, docId) => {
    // 1. 변경된 문서 상세 무효화
    queryClient.invalidateQueries({
      queryKey: documentKeys.detail(docId)
    });
    // 2. 문서 목록 무효화 (상태 변경 반영)
    queryClient.invalidateQueries({
      queryKey: documentKeys.lists()
    });
    // 3. 케이스 정보도 무효화 (completionRate 변경 가능)
    queryClient.invalidateQueries({
      queryKey: caseKeys.all
    });
  },
});
```

### 2.2 WebSocket 이벤트 기반 무효화

```typescript
// WebSocket 이벤트 -> Query 캐시 무효화 매핑

const wsEventToQueryMap: Record<string, QueryKey[]> = {
  'case:created':           [caseKeys.lists()],
  'case:updated':           [caseKeys.all],
  'document:created':       [documentKeys.lists()],
  'document:status_changed': [documentKeys.all, caseKeys.all],
  'review:assigned':        [documentKeys.all],
  'alert:new':              [['alerts']],  // 직접 캐시 주입
  'alert:resolved':         [['alerts']],
  'sync:complete':          [['datasources']],
};
```

### 2.3 수동 무효화 (사용자 액션)

```
새로고침 버튼 클릭 → 해당 페이지의 모든 쿼리 무효화
pull-to-refresh   → 동일
F5 / Cmd+R        → 전체 앱 리로드 (모든 캐시 초기화)
```

---

## 3. 낙관적 업데이트

### 3.1 적용 대상

| 기능 | 액션 | 낙관적 업데이트 | 근거 |
|------|------|----------------|------|
| 문서 상태 변경 | 승인/반려 | 적용 | 즉각적 피드백 필요 |
| 알림 읽음 처리 | 읽음 표시 | 적용 | 빈번한 액션, 실패 드뭄 |
| 케이스 태그 수정 | 태그 추가/제거 | 적용 | 경미한 변경, 빠른 피드백 |
| 문서 내용 저장 | 저장 | 미적용 | 서버 검증 필요, 충돌 가능 |
| 데이터소스 삭제 | 삭제 | 미적용 | 위험한 작업, 확인 필요 |
| OLAP 쿼리 실행 | 쿼리 | 해당 없음 | 서버 계산 필수 |

### 3.2 낙관적 업데이트 패턴

```typescript
const toggleAlertRead = useMutation({
  mutationFn: (alertId: string) => coreApi.markAlertRead(alertId),

  onMutate: async (alertId) => {
    // 1. 진행 중인 쿼리 취소
    await queryClient.cancelQueries({ queryKey: ['alerts', 'feed'] });

    // 2. 이전 데이터 백업
    const previous = queryClient.getQueryData(['alerts', 'feed']);

    // 3. 낙관적으로 캐시 업데이트
    queryClient.setQueryData(['alerts', 'feed'], (old: Alert[]) =>
      old.map(a => a.id === alertId ? { ...a, readAt: new Date().toISOString() } : a)
    );

    // 4. 읽지 않은 카운터 감소
    useUiStore.getState().setUnreadAlertCount(prev => prev - 1);

    return { previous };
  },

  onError: (_err, _alertId, context) => {
    // 실패 시 롤백
    queryClient.setQueryData(['alerts', 'feed'], context?.previous);
    useUiStore.getState().incrementUnreadAlerts();
  },

  onSettled: () => {
    // 서버 데이터로 최종 동기화
    queryClient.invalidateQueries({ queryKey: ['alerts', 'feed'] });
  },
});
```

---

## 4. 프리페칭

### 4.1 라우트 전환 시 프리페치

```typescript
// 케이스 목록에서 케이스 상세로 이동 시 프리페치
function CaseTableRow({ caseItem }: { caseItem: Case }) {
  const queryClient = useQueryClient();

  const handleMouseEnter = () => {
    // 마우스 올림 시 상세 데이터 프리페치
    queryClient.prefetchQuery({
      queryKey: caseKeys.detail(caseItem.id),
      queryFn: () => caseApi.getById(caseItem.id),
      staleTime: 5 * 60 * 1000,
    });
  };

  return (
    <tr onMouseEnter={handleMouseEnter}>
      <td><Link to={`/cases/${caseItem.id}`}>{caseItem.title}</Link></td>
      ...
    </tr>
  );
}
```

---

## 결정 사항 (Decisions)

- 알림은 staleTime: 0, WebSocket이 캐시를 직접 업데이트
  - 근거: 실시간 알림은 항상 최신이어야 함, 폴링 불필요

- OLAP 쿼리는 10분 캐시 (동일 config 기준)
  - 근거: 같은 피벗 설정으로 반복 조회 패턴, 서버 부하 감소

## 금지됨 (Forbidden)

- gcTime을 staleTime보다 작게 설정 (캐시가 fresh 상태에서 GC될 수 있음)
- `queryClient.clear()`를 로그아웃 외 상황에서 호출

---

## 관련 문서

- Core 성능·모니터링 종합 (`services/core/docs/08_operations/performance-monitoring.md`): 멀티레이어 캐시 아키텍처 (L1 TanStack Query → L2 Redis → L3 App → L4 DB), 캐시 히트율 메트릭

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
