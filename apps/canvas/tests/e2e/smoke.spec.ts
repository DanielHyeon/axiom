import { test, expect } from '@playwright/test';

test.describe('Canvas E2E Core Journey Smoke Test', () => {
    test('should navigate through the core journey (Login -> Dashboard -> Cases -> NL2SQL)', async ({ page }) => {
        // 1. Authentication & Entry
        // Although we don't have a real backend, we can test the UI shell
        await page.goto('/login');
        // await expect(page).toHaveTitle(/Axiom/); // Title is temp-canvas

        // Fill login form
        await page.fill('input[type="email"]', 'test-attorney@axiom.ai');
        await page.fill('input[type="password"]', 'password');
        // For now we just click it (assuming mock or no-op login until hooked to real API)
        await page.click('button');

        // Wait for redirect to dashboard
        await page.waitForURL('**/');

        // 2. Dashboard Monitoring
        // Verify Dashboard layout is loaded
        await expect(page.locator('text=대시보드')).toBeVisible();
        await expect(page.locator('text=내 할당 업무')).toBeVisible();

        // Verify mock cases are displayed (from TanStack Query mock `useCases`)
        await expect(page.locator('text=물류최적화 - 현황 분석')).toBeVisible();
        await expect(page.locator('text=신규 공급망 구조 재편')).toBeVisible();

        // 3. Navigate to Documents
        await page.goto('/documents');
        await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible();

        // 4. Navigate to NL2SQL
        // Using side nav link or direct goto to verify Role Guard doesn't kick us out
        // Assuming standard login grants adequate roles in the mock session.
        // If not, we might be redirected. For smoke, we just go to the URL.
        await page.goto('/nl2sql');
        await expect(page.locator('h2').filter({ hasText: 'NL2SQL' })).toBeVisible();
    });
});
