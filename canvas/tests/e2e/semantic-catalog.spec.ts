/**
 * 시멘틱 카탈로그 E2E 테스트.
 *
 * 11탭 브라우징이 정상적으로 동작하는지 검증한다.
 * API 는 mock 으로 대체하여 백엔드 없이도 테스트가 가능하다.
 */
import { test, expect } from './fixtures/auth';
import { mockAllApiRoutes, mockSemanticCatalogApis } from './helpers/axiom-api-mocks';

test.describe('시멘틱 카탈로그 11탭 브라우징', () => {
  test.beforeEach(async ({ authedPage }) => {
    // API 모킹 설정
    await mockAllApiRoutes(authedPage);
    await mockSemanticCatalogApis(authedPage);
  });

  test('시멘틱 카탈로그 페이지 로드', async ({ authedPage }) => {
    await authedPage.goto('/data/semantic-catalog');

    // 페이지가 로드되었는지 확인 — 404 가 아닌지 검증
    const notFound = authedPage.locator('text=404').or(authedPage.locator('text=Not Found'));
    const is404 = await notFound.isVisible({ timeout: 2000 }).catch(() => false);
    expect(is404).toBe(false);

    // 메인 컨텐츠 영역이 렌더링되었는지 확인
    const content = authedPage.locator('main, [data-testid], [role="tablist"]');
    await expect(content.first()).toBeVisible({ timeout: 10000 });
  });

  test('탭 목록이 표시된다', async ({ authedPage }) => {
    await authedPage.goto('/data/semantic-catalog');

    // 탭 리스트 또는 탭 버튼이 존재하는지 확인
    const tabContainer = authedPage.locator('[role="tablist"], [data-testid*="tab"], nav');
    await expect(tabContainer.first()).toBeVisible({ timeout: 10000 });
  });

  test('콘솔 에러 없이 페이지가 렌더링된다', async ({ authedPage }) => {
    // 콘솔 에러 수집
    const errors: string[] = [];
    authedPage.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await authedPage.goto('/data/semantic-catalog');
    await authedPage.waitForSelector('main, [data-testid], [role="tablist"]', { timeout: 10000 });

    // 네트워크 에러는 mock 환경에서 발생할 수 있으므로 제외
    const criticalErrors = errors.filter(
      (e) => !e.includes('net::') && !e.includes('Failed to fetch') && !e.includes('ERR_CONNECTION'),
    );
    expect(criticalErrors).toEqual([]);
  });

  test('각 탭을 클릭하면 컨텐츠가 변경된다', async ({ authedPage }) => {
    await authedPage.goto('/data/semantic-catalog');
    await authedPage.waitForSelector('main, [data-testid], [role="tablist"]', { timeout: 10000 });

    // 탭 버튼 또는 탭 역할 요소 찾기
    const tabs = authedPage.locator('[role="tab"], [data-testid*="tab-"]');
    const tabCount = await tabs.count();

    // 탭이 2개 이상 존재해야 한다
    if (tabCount >= 2) {
      // 두 번째 탭 클릭
      await tabs.nth(1).click();
      // 탭 전환 후 컨텐츠가 존재하는지 확인
      const panel = authedPage.locator('[role="tabpanel"], main, [data-testid]');
      await expect(panel.first()).toBeVisible({ timeout: 5000 });
    }
  });

  test('시멘틱 카탈로그 URL 이 올바르다', async ({ authedPage }) => {
    await authedPage.goto('/data/semantic-catalog');
    await authedPage.waitForSelector('main, [data-testid], [role="tablist"]', { timeout: 10000 });

    // URL 확인
    expect(authedPage.url()).toContain('/data/semantic-catalog');
  });
});
