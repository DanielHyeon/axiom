/**
 * axe-core 접근성 자동 스캔 헬퍼.
 * Phase 2: 컴포넌트 테스트에서 `expectNoA11yViolations(container)` 호출.
 *
 * 사용법:
 *   import { expectNoA11yViolations } from '@/test/axe-helper';
 *   it('접근성 위반 없음', async () => {
 *     const { container } = render(<MyComponent />);
 *     await expectNoA11yViolations(container);
 *   });
 *
 * 설치 필요: npm install -D axe-core
 * axe-core 미설치 시 테스트를 skip한다 (CI에서 실패하지 않음).
 */

import { expect } from 'vitest';

let axeRun: ((node: Element) => Promise<{ violations: Array<{ id: string; impact?: string; description: string; nodes: Array<{ html: string }> }> }>) | null = null;

try {
  // 동적 import — axe-core 미설치 시 null 유지
  const axe = await import('axe-core');
  axeRun = (node: Element) => axe.default.run(node);
} catch {
  // axe-core 미설치 — graceful skip
}

/**
 * 컨테이너에 대해 axe-core 접근성 스캔을 실행한다.
 * Critical/Serious 위반이 있으면 테스트 실패.
 * axe-core 미설치 시 경고만 출력하고 통과.
 */
export async function expectNoA11yViolations(container: Element): Promise<void> {
  if (!axeRun) {
    console.warn('[axe-helper] axe-core 미설치 — 접근성 검사 스킵. `npm install -D axe-core`로 설치하세요.');
    return;
  }

  const results = await axeRun(container);
  const critical = results.violations.filter(
    (v) => v.impact === 'critical' || v.impact === 'serious'
  );

  if (critical.length > 0) {
    const summary = critical
      .map((v) => `[${v.impact}] ${v.id}: ${v.description}\n  ${v.nodes.map((n) => n.html).join('\n  ')}`)
      .join('\n\n');
    expect.fail(`접근성 위반 ${critical.length}건 발견:\n\n${summary}`);
  }
}
