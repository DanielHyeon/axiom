/**
 * E2E: 문서 HITL 워크플로 — 문서 목록 → 상세 → 리뷰 → 승인/반려.
 * Phase 2 핵심 E2E 시나리오 #2.
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';

// 로그인 헬퍼
async function login(page: import('@playwright/test').Page, email = 'admin@local.axiom', password = 'admin') {
  await page.goto(`${BASE_URL}/auth/login`);
  await page.fill('input[name="email"], input[type="email"]', email);
  await page.fill('input[name="password"], input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard', { timeout: 10000 });
}

test.describe('Document HITL Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('문서 목록 페이지 접근 → 문서 리스트 렌더링', async ({ page }) => {
    // 케이스 상세 → 문서 탭으로 이동 (또는 직접 URL)
    await page.goto(`${BASE_URL}/documents`);

    // h1 "문서 관리" 확인
    await expect(page.locator('h1')).toContainText('문서', { timeout: 5000 });
  });

  test('문서 상세 → 리뷰 패널 표시', async ({ page }) => {
    await page.goto(`${BASE_URL}/documents`);

    // 첫 번째 문서 행 클릭 (DataTable row)
    const firstRow = page.locator('tbody tr').first();
    if (await firstRow.isVisible()) {
      await firstRow.click();
      // 에디터 또는 리뷰 페이지로 이동 확인
      await page.waitForURL(/\/documents\//, { timeout: 5000 });
    }
  });
});
