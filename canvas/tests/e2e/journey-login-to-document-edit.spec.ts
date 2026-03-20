import { test, expect } from '@playwright/test';

/**
 * 1-G5: 로그인 → 대시보드 → 케이스 목록 → 케이스 상세 → 문서 목록 → 문서 편집
 */
test.describe('Journey: Login to Document Edit', () => {
  test('login -> dashboard -> cases list -> case detail -> documents list -> document edit', async ({
    page,
  }) => {
    // 1. 로그인
    await page.goto('/auth/login');
    await page.fill('input[type="email"]', 'admin@axiom.ai');
    await page.fill('input[type="password"]', 'password');
    await page.click('button[type="submit"]');

    // 2. 대시보드로 리다이렉트
    await page.waitForURL(/\/(dashboard)?$/);
    await expect(page.locator('text=대시보드').or(page.locator('text=전체 케이스'))).toBeVisible();

    // 3. 케이스 목록
    await page.goto('/cases');
    await expect(page.getByRole('heading', { name: '케이스 목록' })).toBeVisible();
    await expect(page.locator('text=물류최적화 - 현황 분석')).toBeVisible();

    // 4. 첫 번째 케이스 행 클릭 -> 상세
    await page.locator('tbody tr').first().click();
    await expect(page).toHaveURL(/\/cases\/[^/]+$/);
    await expect(page.locator('text=물류최적화 - 현황 분석').or(page.locator('text=케이스 상세'))).toBeVisible();

    // 5. "문서" 링크 클릭 -> 문서 목록
    await page.getByRole('link', { name: '문서' }).click();
    await expect(page).toHaveURL(/\/cases\/[^/]+\/documents$/);
    await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible();

    // 6. 첫 번째 문서 행 클릭 -> 문서 편집
    await page.locator('tbody tr').first().click();
    await expect(page).toHaveURL(/\/cases\/[^/]+\/documents\/[^/]+$/);
    // 편집 페이지: 모나코 에디터 또는 문서 제목/편집 UI
    await expect(
      page.locator('.monaco-editor').or(page.locator('text=이해관계자목록v3')).first()
    ).toBeVisible({ timeout: 15000 });
  });
});
