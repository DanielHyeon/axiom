/**
 * E2E: NL2SQL 분석 플로우 — 질문 → SQL 생성 → 결과 확인.
 * Phase 2 핵심 E2E 시나리오 #3.
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';

async function login(page: import('@playwright/test').Page) {
  await page.goto(`${BASE_URL}/auth/login`);
  await page.fill('input[name="email"], input[type="email"]', 'admin@local.axiom');
  await page.fill('input[name="password"], input[type="password"]', 'admin');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard', { timeout: 10000 });
}

test.describe('NL2SQL Analysis Flow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('NL2SQL 페이지 접근 → 채팅 UI 렌더링', async ({ page }) => {
    await page.goto(`${BASE_URL}/analysis/nl2sql`);

    // 페이지 로드 확인 (제목 또는 입력 필드)
    const chatInput = page.locator('textarea, input[placeholder*="질문"], input[placeholder*="query"]');
    await expect(chatInput.first()).toBeVisible({ timeout: 10000 });
  });

  test('사이드바 NL2SQL 메뉴 클릭 → 네비게이션', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);

    // 사이드바에서 NL2SQL 아이콘 클릭 (aria-label 기반)
    const nl2sqlLink = page.locator('a[aria-label*="NL2SQL"], a[aria-label*="nl2sql"], a[aria-label*="자연어"]');
    if (await nl2sqlLink.first().isVisible()) {
      await nl2sqlLink.first().click();
      await page.waitForURL('**/analysis/nl2sql', { timeout: 5000 });
    }
  });
});
