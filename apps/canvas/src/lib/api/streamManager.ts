import { useAuthStore } from '@/stores/authStore';

/**
 * POST 기반 스트림 (fetch + ReadableStream). LLM/ReAct 등 요청 단위 스트림용.
 * @see docs/04_frontend/event-streams.md
 */

export interface StreamOptions<T> {
  onMessage: (data: T) => void;
  onComplete: () => void;
  onError: (error: Error) => void;
}

/**
 * Plain text SSE 스트림 (LLM 응답 등). 각 청크를 문자열로 전달.
 */
export async function createTextStream(
  url: string,
  body: Record<string, unknown>,
  options: StreamOptions<string>
): Promise<AbortController> {
  return createStream(url, body, options, 'text');
}

/**
 * NDJSON 스트림 (ReAct 추론 등). 각 줄을 JSON 파싱하여 객체로 전달.
 */
export async function createNdjsonStream<T = Record<string, unknown>>(
  url: string,
  body: Record<string, unknown>,
  options: StreamOptions<T>
): Promise<AbortController> {
  return createStream(url, body, options, 'ndjson');
}

async function createStream<T>(
  url: string,
  body: Record<string, unknown>,
  options: StreamOptions<T>,
  mode: 'text' | 'ndjson'
): Promise<AbortController> {
  const controller = new AbortController();
  const token = useAuthStore.getState().accessToken;

  (async () => {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          Accept: mode === 'ndjson' ? 'application/x-ndjson' : 'text/event-stream',
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Stream failed: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        options.onComplete();
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          options.onComplete();
          break;
        }

        const chunk = decoder.decode(value, { stream: true });

        if (mode === 'text') {
          (options.onMessage as (data: string) => void)(chunk);
        } else {
          buffer += chunk;
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';
          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              (options.onMessage as (data: T) => void)(JSON.parse(line) as T);
            } catch {
              // skip malformed line
            }
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        options.onError(error as Error);
      }
    }
  })();

  return controller;
}
