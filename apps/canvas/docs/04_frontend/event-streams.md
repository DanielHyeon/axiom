# 이벤트·스트림 매니저 표준

Canvas에서 실시간/스트리밍 데이터는 다음 두 패턴으로 구분한다. WebSocket은 현재 미사용이며, 필요 시 별도 모듈로 추가한다.

---

## 1. 요약

| 용도 | 모듈 | 프로토콜 | 생명주기 | 파일 |
|------|------|----------|----------|------|
| **Watch 알림** | watchStream | GET SSE (EventSource) | 앱/페이지 단일 연결, 구독 해제 시 정리 | `src/lib/api/watchStream.ts` |
| **LLM/ReAct 스트림** | streamManager | POST + ReadableStream | 요청 단위, AbortController로 취소 | `src/lib/api/streamManager.ts` |

---

## 2. Watch 스트림 (EventSource)

- **역할**: Core `GET /api/v1/watches/stream` 구독. 이벤트 타입 `alert`, `alert_update`, `heartbeat`.
- **모듈**: `@/lib/api/watchStream`
- **API**:
  - `subscribeWatchStream(baseUrl, token, callbacks)` → `() => void` (unsubscribe).
  - `disconnectWatchStream()` — 수동 해제용.
- **규칙**:
  - 전역 단일 연결. 새 구독 시 기존 연결을 끊고 새로 연결.
  - 컴포넌트 언마운트 시 반환된 unsubscribe 함수 호출 필수.
- **레거시**: `wsManager.ts`는 deprecated re-export만 유지. 신규 코드는 `watchStream` 직접 사용.

---

## 3. POST 스트림 (fetch + ReadableStream)

- **역할**: LLM 스트리밍, ReAct NDJSON 등 **요청 한 번당** 스트림. POST body로 파라미터 전달.
- **모듈**: `@/lib/api/streamManager`
- **API**:
  - `createTextStream(url, body, options)` → `Promise<AbortController>` (청크가 문자열).
  - `createNdjsonStream<T>(url, body, options)` → `Promise<AbortController>` (청크가 JSON 객체).
- **규칙**:
  - 반환된 `AbortController.abort()`로 취소. 컴포넌트 언마운트 시 abort 호출 권장.
  - 인증: `useAuthStore.getState().accessToken`으로 Authorization 헤더 주입.

---

## 4. 사용처

- **watchStream**: `features/watch/hooks/useAlerts.ts` — 실시간 알림 수신.
- **streamManager**: NL2SQL ReAct 스트림 등 (해당 API 호출부).

---

## 5. WebSocket

현재 Canvas에는 WebSocket 연결이 없음. 추후 실시간 협업·프로세스 이벤트 등이 필요하면 별도 `webSocketManager`(또는 도메인별 모듈)를 두고, 이 문서에 사용처·생명주기 규칙을 추가할 것.
