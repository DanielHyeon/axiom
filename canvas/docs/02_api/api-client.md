# API 클라이언트 설계

<!-- affects: frontend, api -->
<!-- requires-update: 01_architecture/api-integration.md, 07_security/auth-flow.md -->

## 이 문서가 답하는 질문

- Canvas의 API 클라이언트는 어떻게 구성되는가?
- Axios 인스턴스 팩토리의 구조는?
- 인터셉터는 어떤 역할을 하며, 어떤 순서로 동작하는가?
- 에러 핸들링은 어떻게 표준화되는가?
- K-AIR의 Axios 기반 API 클라이언트와 무엇이 달라지는가?

---

## 1. 클라이언트 팩토리

### 1.1 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│  createApiClient(baseURL)                                     │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Axios 인스턴스                                          │ │
│  │                                                          │ │
│  │  Request Interceptors (요청 인터셉터)                    │ │
│  │  ┌────────────────────────────────────────────────────┐ │ │
│  │  │ 1. Auth Interceptor                                │ │ │
│  │  │    - Authorization: Bearer {accessToken}           │ │ │
│  │  │    - 토큰 없으면 요청 그대로 통과                   │ │ │
│  │  ├────────────────────────────────────────────────────┤ │ │
│  │  │ 2. Tenant Interceptor                              │ │ │
│  │  │    - X-Tenant-Id: {tenantId}                       │ │ │
│  │  │    - 멀티테넌트 식별                                │ │ │
│  │  ├────────────────────────────────────────────────────┤ │ │
│  │  │ 3. Request Logger                                  │ │ │
│  │  │    - 개발 모드에서만 요청 로깅                      │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  │                                                          │ │
│  │  Response Interceptors (응답 인터셉터)                   │ │
│  │  ┌────────────────────────────────────────────────────┐ │ │
│  │  │ 1. Response Unwrapper                              │ │ │
│  │  │    - ApiResponse<T>.data 추출                      │ │ │
│  │  │    - meta 정보 헤더 매핑                            │ │ │
│  │  ├────────────────────────────────────────────────────┤ │ │
│  │  │ 2. Error Normalizer                                │ │ │
│  │  │    - HTTP 에러 -> AppError 변환                    │ │ │
│  │  │    - 네트워크 에러 처리                             │ │ │
│  │  ├────────────────────────────────────────────────────┤ │ │
│  │  │ 3. Auth Error Handler                              │ │ │
│  │  │    - 401 -> 토큰 리프레시 -> 원래 요청 재시도      │ │ │
│  │  │    - 리프레시 실패 -> 로그아웃                      │ │ │
│  │  ├────────────────────────────────────────────────────┤ │ │
│  │  │ 4. Response Logger                                 │ │ │
│  │  │    - 개발 모드에서만 응답 로깅                      │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  반환: 설정된 Axios 인스턴스                                  │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 구현 상세

```typescript
// lib/api/createApiClient.ts

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/authStore';
import { AppError, normalizeError } from './errors';

interface ApiClientConfig {
  baseURL: string;
  timeout?: number;
}

export function createApiClient(baseURL: string, config?: Partial<ApiClientConfig>): AxiosInstance {
  const instance = axios.create({
    baseURL: `${baseURL}/api/v1`,
    timeout: config?.timeout ?? 30_000,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  });

  // === Request Interceptors ===

  // 1. Auth Interceptor
  instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  // 2. Tenant Interceptor
  instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const tenantId = useAuthStore.getState().user?.tenantId;
    if (tenantId) {
      config.headers['X-Tenant-Id'] = tenantId;
    }
    return config;
  });

  // === Response Interceptors ===

  // 1. Response Unwrapper
  instance.interceptors.response.use(
    (response) => {
      // ApiResponse<T> 형식이면 data 추출
      if (response.data?.success !== undefined) {
        return { ...response, data: response.data.data };
      }
      return response;
    }
  );

  // 2. Auth Error Handler (401 -> 리프레시)
  instance.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config;
      if (!originalRequest) return Promise.reject(error);

      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;
        try {
          const newToken = await useAuthStore.getState().refreshAccessToken();
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return instance(originalRequest);
        } catch {
          useAuthStore.getState().logout();
          window.location.href = '/login';
          return Promise.reject(error);
        }
      }

      return Promise.reject(normalizeError(error));
    }
  );

  return instance;
}
```

---

## 2. 에러 처리

### 2.1 에러 타입 체계

```typescript
// lib/api/errors.ts

export class AppError extends Error {
  constructor(
    public code: string,
    public message: string,
    public status: number,
    public details?: Record<string, string[]>,
    public originalError?: unknown,
  ) {
    super(message);
    this.name = 'AppError';
  }

  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get isValidationError(): boolean {
    return this.status === 422;
  }

  get isServerError(): boolean {
    return this.status >= 500;
  }

  get isNetworkError(): boolean {
    return this.code === 'NETWORK_ERROR';
  }
}

export function normalizeError(error: AxiosError): AppError {
  // 네트워크 에러 (서버 응답 없음)
  if (!error.response) {
    return new AppError(
      'NETWORK_ERROR',
      '네트워크 연결을 확인해 주세요.',
      0,
      undefined,
      error,
    );
  }

  const { status, data } = error.response;
  const apiError = data as { error?: { code: string; message: string; details?: Record<string, string[]> } };

  return new AppError(
    apiError?.error?.code || `HTTP_${status}`,
    apiError?.error?.message || getDefaultMessage(status),
    status,
    apiError?.error?.details,
    error,
  );
}

function getDefaultMessage(status: number): string {
  const messages: Record<number, string> = {
    400: '잘못된 요청입니다.',
    401: '인증이 필요합니다. 다시 로그인해 주세요.',
    403: '이 작업을 수행할 권한이 없습니다.',
    404: '요청한 리소스를 찾을 수 없습니다.',
    409: '데이터 충돌이 발생했습니다. 새로고침 후 다시 시도해 주세요.',
    422: '입력 데이터를 확인해 주세요.',
    429: '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.',
    500: '서버 오류가 발생했습니다.',
    502: '서버에 연결할 수 없습니다.',
    503: '서비스가 일시적으로 사용 불가능합니다.',
  };
  return messages[status] || '알 수 없는 오류가 발생했습니다.';
}
```

### 2.2 에러 처리 흐름

```
Axios 에러 발생
    │
    ▼
[normalizeError()] ──→ AppError 생성
    │
    ▼
TanStack Query onError
    │
    ├── isValidationError (422)
    │     └── 폼 필드에 에러 메시지 표시
    │         (React Hook Form setError)
    │
    ├── isAuthError (401/403)
    │     └── 토스트 알림 + 필요 시 리다이렉트
    │
    ├── isNetworkError
    │     └── 오프라인 배너 표시
    │         (Zustand uiStore.isOffline = true)
    │
    └── isServerError (500+)
          └── 토스트 알림 + 재시도 안내
```

---

## 3. WebSocket 매니저

### 3.1 구조

```typescript
// lib/api/wsManager.ts

class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private listeners = new Map<string, Set<(data: unknown) => void>>();

  connect(token: string): void {
    const url = `${import.meta.env.VITE_WS_URL}?token=${token}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      console.info('[WS] Connected');
    };

    this.ws.onmessage = (event) => {
      const { type, payload } = JSON.parse(event.data);
      this.emit(type, payload);
    };

    this.ws.onclose = (event) => {
      if (!event.wasClean) {
        this.scheduleReconnect(token);
      }
    };
  }

  private scheduleReconnect(token: string): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached');
      return;
    }
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000);
    this.reconnectAttempts++;
    setTimeout(() => this.connect(token), delay);
  }

  on(event: string, callback: (data: unknown) => void): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);

    // unsubscribe 함수 반환
    return () => this.listeners.get(event)?.delete(callback);
  }

  private emit(event: string, data: unknown): void {
    this.listeners.get(event)?.forEach((cb) => cb(data));
  }

  disconnect(): void {
    this.ws?.close(1000, 'Client disconnect');
    this.ws = null;
    this.listeners.clear();
  }
}

export const wsManager = new WebSocketManager();
```

### 3.2 WebSocket 이벤트 타입

| 이벤트 | 페이로드 | 구독 Feature |
|--------|----------|-------------|
| `case:created` | `{ caseId, title }` | case-dashboard |
| `case:updated` | `{ caseId, status, changes }` | case-dashboard |
| `document:created` | `{ documentId, caseId }` | document-management |
| `document:status_changed` | `{ documentId, oldStatus, newStatus }` | document-management |
| `review:assigned` | `{ reviewId, documentId, assigneeId }` | document-management |
| `alert:new` | `{ alertId, type, severity, message }` | watch-alerts |
| `alert:resolved` | `{ alertId }` | watch-alerts |
| `sync:progress` | `{ datasourceId, progress, stage }` | datasource-manager |

---

## 4. SSE 매니저

### 4.1 구조

```typescript
// lib/api/sseManager.ts

interface SSEConfig {
  url: string;
  token: string;
  onMessage: (event: string, data: unknown) => void;
  onError?: (error: Event) => void;
  onComplete?: () => void;
}

export function createSSEConnection(config: SSEConfig): () => void {
  const eventSource = new EventSource(config.url, {
    // 브라우저 기본 EventSource는 헤더 설정 불가
    // 대안: fetch + ReadableStream 또는 @microsoft/fetch-event-source
  });

  eventSource.onmessage = (event) => {
    if (event.data === '[DONE]') {
      config.onComplete?.();
      eventSource.close();
      return;
    }
    const parsed = JSON.parse(event.data);
    config.onMessage(parsed.type || 'message', parsed);
  };

  eventSource.onerror = (error) => {
    config.onError?.(error);
    eventSource.close();
  };

  // cleanup 함수 반환
  return () => eventSource.close();
}
```

---

## 5. K-AIR API 패턴 비교

| 항목 | K-AIR | Canvas |
|------|-------|--------|
| HTTP 클라이언트 | Axios (직접 사용) | Axios (팩토리 + 인터셉터) |
| 인증 | Keycloak 토큰 수동 첨부 | Auth Interceptor 자동 |
| 에러 처리 | try-catch per component | normalizeError + TanStack Query |
| 실시간 | Socket.io | 네이티브 WebSocket |
| 스트리밍 | SSE (직접 EventSource) | SSE Manager (fetch-event-source) |
| 타입 안전성 | 부분적 (any 사용) | 전체 TypeScript strict |
| 멀티 백엔드 | BackendFactory (런타임) | 환경 변수 (컴파일 타임) |

---

## 결정 사항 (Decisions)

- Socket.io 대신 네이티브 WebSocket 사용
  - 근거: Socket.io의 프로토콜 오버헤드 불필요, 서버 호환성 단순화
  - 재평가 조건: 룸(Room) 기반 구독이 필요해지면 Socket.io 재검토

- fetch-event-source 라이브러리 사용 (SSE + 인증 헤더)
  - 근거: 브라우저 네이티브 EventSource는 커스텀 헤더 불가
  - 대안: 쿼리 파라미터에 토큰 전달 (보안 약점)

## 금지됨 (Forbidden)

- 컴포넌트에서 Axios 인스턴스 직접 생성
- API 함수에서 에러를 삼키기 (catch 후 조용히 무시)
- WebSocket 이벤트에서 직접 setState (반드시 Zustand 또는 TanStack Query를 통해)

## 필수 (Required)

- 모든 API 함수는 반환 타입을 명시 (`Promise<Case[]>`, `Promise<Document>`)
- 에러는 AppError 형태로 정규화
- WebSocket/SSE 연결은 cleanup 함수를 반환하여 메모리 누수 방지

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
