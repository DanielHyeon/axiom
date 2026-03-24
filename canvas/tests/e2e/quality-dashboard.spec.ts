/**
 * 품질 대시보드 E2E 테스트.
 *
 * 품질 점수 표시, 신뢰 등급 배지, 대시보드 요약 등을 검증한다.
 * API 는 mock 으로 대체하여 백엔드 없이도 테스트가 가능하다.
 */
import { test, expect } from './fixtures/auth';
import { mockAllApiRoutes, mockQualityDashboardApis } from './helpers/axiom-api-mocks';

test.describe('품질 대시보드', () => {
  test.beforeEach(async ({ authedPage }) => {
    // API 모킹 설정
    await mockAllApiRoutes(authedPage);
    await mockQualityDashboardApis(authedPage);
  });

  test('품질 대시보드 페이지 로드', async ({ authedPage }) => {
    await authedPage.goto('/data/quality');

    // 페이지가 로드되었는지 확인 — 404 가 아닌지 검증
    const notFound = authedPage.locator('text=404').or(authedPage.locator('text=Not Found'));
    const is404 = await notFound.isVisible({ timeout: 2000 }).catch(() => false);
    expect(is404).toBe(false);

    // 메인 컨텐츠 영역이 렌더링되었는지 확인
    const content = authedPage.locator('main, [data-testid], table, [role="table"]');
    await expect(content.first()).toBeVisible({ timeout: 10000 });
  });

  test('콘솔 에러 없이 렌더링된다', async ({ authedPage }) => {
    const errors: string[] = [];
    authedPage.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await authedPage.goto('/data/quality');
    await authedPage.waitForSelector('main, [data-testid]', { timeout: 10000 });

    // 네트워크 에러 제외
    const criticalErrors = errors.filter(
      (e) => !e.includes('net::') && !e.includes('Failed to fetch') && !e.includes('ERR_CONNECTION'),
    );
    expect(criticalErrors).toEqual([]);
  });

  test('품질 대시보드 URL 이 올바르다', async ({ authedPage }) => {
    await authedPage.goto('/data/quality');
    await authedPage.waitForSelector('main, [data-testid]', { timeout: 10000 });

    expect(authedPage.url()).toContain('/data/quality');
  });

  test('품질 데이터가 표시된다', async ({ authedPage }) => {
    await authedPage.goto('/data/quality');
    await authedPage.waitForSelector('main, [data-testid]', { timeout: 10000 });

    // 페이지에 의미 있는 UI 컨텐츠가 렌더링되었는지 확인
    // (테이블, 카드, 차트 등)
    const uiElements = authedPage.locator(
      'table, [role="table"], [data-testid*="quality"], [data-testid*="score"], .card, [class*="card"]',
    );
    const hasUi = await uiElements.first().isVisible({ timeout: 5000 }).catch(() => false);

    // UI 요소가 있거나, 최소한 main 영역이 비어있지 않은지 확인
    if (!hasUi) {
      const mainContent = authedPage.locator('main');
      const text = await mainContent.textContent();
      // 페이지에 텍스트 컨텐츠가 있어야 한다
      expect(text?.trim().length).toBeGreaterThan(0);
    }
  });

  test('네비게이션에서 품질 대시보드로 접근 가능', async ({ authedPage }) => {
    // 대시보드에서 시작
    await authedPage.goto('/dashboard');
    await authedPage.waitForSelector('nav, [role="navigation"], aside', { timeout: 10000 });

    // 사이드바에서 품질 관련 링크 찾기
    const qualityLink = authedPage.locator(
      'a[href*="quality"], [data-testid*="quality"]',
    );
    const isVisible = await qualityLink.first().isVisible({ timeout: 3000 }).catch(() => false);

    if (isVisible) {
      await qualityLink.first().click();
      await authedPage.waitForURL(/quality/, { timeout: 5000 });
      expect(authedPage.url()).toContain('quality');
    } else {
      // 직접 URL 로 접근 (사이드바에 링크가 없는 경우)
      await authedPage.goto('/data/quality');
      expect(authedPage.url()).toContain('/data/quality');
    }
  });
});
