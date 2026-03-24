/**
 * 청크 로딩 실패 시 자동으로 재시도하는 lazy 래퍼.
 *
 * 배포 직후 브라우저에 캐시된 구버전 청크 해시와 서버의 신버전 해시가
 * 달라서 import()가 실패하는 문제를 해결한다.
 *
 * 동작 순서:
 * 1. factory()를 호출하여 청크를 로딩한다.
 * 2. 실패하면 interval(ms)만큼 기다린 뒤 retries 횟수만큼 재시도한다.
 * 3. 모든 재시도가 실패하면 페이지를 한 번 새로고침한다.
 * 4. 새로고침 후에도 실패하면 에러를 그대로 던진다 (무한 루프 방지).
 */
import { lazy, type ComponentType } from 'react';

// 새로고침 중복 방지를 위한 sessionStorage 키
const RELOAD_KEY = 'axiom_chunk_reload';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function lazyWithRetry<T extends ComponentType<any>>(
  factory: () => Promise<{ default: T }>,
  retries = 2,
  interval = 1500,
): React.LazyExoticComponent<T> {
  return lazy(async () => {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const module = await factory();
        // 성공한 뒤에 새로고침 플래그를 지운다 (import 전에 지우면 이중 reload 위험)
        sessionStorage.removeItem(RELOAD_KEY);
        return module;
      } catch (error) {
        if (attempt === retries) {
          // 이미 새로고침한 적이 있으면 무한 루프 방지를 위해 에러를 던진다
          if (sessionStorage.getItem(RELOAD_KEY)) {
            sessionStorage.removeItem(RELOAD_KEY);
            throw error;
          }
          // 마지막 시도 실패 → 페이지 새로고침으로 최신 청크를 가져온다
          sessionStorage.setItem(RELOAD_KEY, '1');
          window.location.reload();
          throw error;
        }
        // 재시도 전 잠시 대기
        await new Promise((r) => setTimeout(r, interval));
      }
    }
    // 이론적으로 도달할 수 없는 코드
    throw new Error('lazyWithRetry: unreachable');
  });
}
