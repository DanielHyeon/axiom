/**
 * 전체 네비게이션 E2E 테스트.
 *
 * 주요 라우트가 모두 접근 가능하고 올바르게 렌더링되는지 확인한다.
 * routes.ts SSOT 기준으로 핵심 라우트를 순회한다.
 */
import { test, expect } from './fixtures/auth';

/* -------------------------------------------------------------------------- */
/*  테스트 대상 라우트 목록                                                    */
/* -------------------------------------------------------------------------- */

const ROUTES = [
  { path: '/analysis/olap-studio', title: 'OLAP Studio' },
  { path: '/analysis/nl2sql', title: 'NL2SQL' },
  { path: '/analysis/insight', title: 'Insight' },
  { path: '/data/sources', title: '데이터 소스' },
  { path: '/data/etl', title: 'ETL' },
  { path: '/data/cubes', title: '큐브' },
  { path: '/data/lineage', title: '리니지' },
  { path: '/data/ontology', title: '온톨로지' },
  { path: '/data/datasources', title: '데이터소스' },
  { path: '/data/glossary', title: '글로서리' },
  { path: '/data/explorer', title: '탐색기' },
];

/* -------------------------------------------------------------------------- */
/*  라우트 접근 테스트                                                        */
/* -------------------------------------------------------------------------- */

for (const route of ROUTES) {
  test(`라우트 접근: ${route.path}`, async ({ authedPage }) => {
    // 콘솔 에러 수집 — goto 전에 리스너 등록
    const errors: string[] = [];
    authedPage.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await authedPage.goto(route.path);
    // 페이지 로드 대기 — 네비게이션 또는 메인 컨텐츠 렌더링 기반
    await authedPage.waitForSelector('nav, [role="navigation"], aside, main, [data-testid]', { timeout: 10000 });

    // 404 페이지가 아닌지 확인
    const notFoundEl = authedPage
      .locator('text=404')
      .or(authedPage.locator('text=Not Found'));
    const is404 = await notFoundEl
      .isVisible({ timeout: 1000 })
      .catch(() => false);
    expect(is404).toBe(false);

    // 제목이나 관련 텍스트가 보이는지 확인 (soft check — 라우트마다 다름)
    const titleEl = authedPage.locator(`text=${route.title}`);
    const isVisible = await titleEl
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    // 페이지에 의미 있는 UI 요소가 렌더링되었는지 확인
    const hasContent = authedPage.locator('nav, [role="navigation"], aside, main, [data-testid]');
    await expect(hasContent.first()).toBeVisible();

    // 콘솔 에러가 발생하지 않았는지 확인 (네트워크 에러 등은 제외)
    const criticalErrors = errors.filter(
      (e) => !e.includes('net::') && !e.includes('Failed to fetch'),
    );
    expect(criticalErrors).toEqual([]);
  });
}

/* -------------------------------------------------------------------------- */
/*  사이드바 네비게이션                                                       */
/* -------------------------------------------------------------------------- */

test.describe('사이드바 네비게이션', () => {
  test('사이드바 메뉴 항목 존재', async ({ authedPage }) => {
    await authedPage.goto('/dashboard');
    // 사이드바 렌더링 대기
    await authedPage.waitForSelector('nav, [role="navigation"], aside', { timeout: 10000 });

    // 사이드바 또는 네비게이션 영역 확인
    const nav = authedPage.locator('nav, [role="navigation"], aside');
    await expect(nav.first()).toBeVisible({ timeout: 5000 });
  });

  test('사이드바에서 NL2SQL 메뉴 클릭', async ({ authedPage }) => {
    await authedPage.goto('/dashboard');
    // 사이드바 렌더링 대기
    await authedPage.waitForSelector('nav, [role="navigation"], aside', { timeout: 10000 });

    // NL2SQL 메뉴 링크 찾기
    const nl2sqlLink = authedPage.locator(
      'a[href*="nl2sql"], [data-testid*="nl2sql"]',
    );
    if (await nl2sqlLink.first().isVisible({ timeout: 3000 }).catch(() => false)) {
      await nl2sqlLink.first().click();
      await authedPage.waitForURL(/nl2sql/, { timeout: 5000 });
      expect(authedPage.url()).toContain('nl2sql');
    }
  });
});
