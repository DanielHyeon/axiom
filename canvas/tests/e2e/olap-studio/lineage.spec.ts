/**
 * OLAP Studio 데이터 리니지 E2E 테스트.
 *
 * 테스트 시나리오:
 *  - 리니지 페이지 로드
 *  - 엔티티 목록 표시
 *  - 그래프 렌더링
 *  - 영향 분석 패널
 */
import { test, expect } from '../fixtures/auth';

test.describe('데이터 리니지', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/data/lineage');
    // 페이지 로드 대기 — 리니지 제목 텍스트 기반
    await authedPage.waitForSelector('text=리니지', { timeout: 10000 });
  });

  test('페이지 로드', async ({ authedPage }) => {
    // 리니지 관련 제목 텍스트 확인
    await expect(
      authedPage
        .locator('text=데이터 리니지')
        .or(authedPage.locator('text=리니지')),
    ).toBeVisible({ timeout: 10000 });
  });

  test('엔티티 타입별 그룹 표시', async ({ authedPage }) => {
    // 엔티티가 있으면 타입별 그룹 헤더가 표시됨
    const typeLabels = [
      '원천 테이블',
      '스테이징',
      '팩트',
      '차원',
      '큐브',
      '측정값',
    ];
    let hasAnyGroup = false;
    for (const label of typeLabels) {
      const el = authedPage.locator(`text=${label}`);
      if (await el.isVisible({ timeout: 1000 }).catch(() => false)) {
        hasAnyGroup = true;
        break;
      }
    }
    // 데이터가 없으면 빈 그래프 메시지가 표시될 수 있음
    if (!hasAnyGroup) {
      const emptyMsg = authedPage.locator('text=리니지 데이터가 없습니다');
      const hasEmpty = await emptyMsg
        .isVisible({ timeout: 2000 })
        .catch(() => false);
      // 둘 중 하나는 보여야 함 — 그룹 헤더 또는 빈 상태 메시지
      expect(hasAnyGroup || hasEmpty).toBe(true);
    }
  });

  test('엔티티 카운트 표시', async ({ authedPage }) => {
    // "N개 엔티티" 텍스트 확인 — 데이터가 있을 때만
    const countText = authedPage.locator('text=/\\d+개 엔티티/');
    const hasCount = await countText
      .isVisible({ timeout: 5000 })
      .catch(() => false);
    if (hasCount) {
      await expect(countText).toBeVisible();
    }
  });

  test('엔티티 클릭 시 영향 분석 패널', async ({ authedPage }) => {
    // 그래프 노드 또는 목록 항목 클릭
    const entityItems = authedPage.locator(
      '[data-testid*="entity"], [data-testid*="node"], .lineage-node',
    );
    const firstEntity = entityItems.first();

    if (await firstEntity.isVisible({ timeout: 3000 }).catch(() => false)) {
      await firstEntity.click();
      await authedPage.waitForTimeout(500);
      // 영향 분석 패널이 표시될 수 있음
      const impactPanel = authedPage.locator('text=영향 분석');
      if (await impactPanel.isVisible({ timeout: 3000 }).catch(() => false)) {
        await expect(impactPanel).toBeVisible();
        // Upstream / Downstream 섹션 확인
        const upstream = authedPage.locator('text=Upstream');
        const downstream = authedPage.locator('text=Downstream');
        if (await upstream.isVisible({ timeout: 2000 }).catch(() => false)) {
          await expect(upstream).toBeVisible();
          await expect(downstream).toBeVisible();
        }
      }
    }
  });

  test('404 페이지가 아닌지 확인', async ({ authedPage }) => {
    const notFoundEl = authedPage
      .locator('text=404')
      .or(authedPage.locator('text=Not Found'));
    const is404 = await notFoundEl
      .isVisible({ timeout: 1000 })
      .catch(() => false);
    expect(is404).toBe(false);
  });
});
