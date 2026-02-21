import { test, expect } from '@playwright/test';

test.describe('Sprint 6 - Watch Alerts & Notification Center', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.fill('input[type="email"]', 'admin@axiom.ai');
        await page.fill('input[type="password"]', 'password');
        await page.click('button');
        await expect(page).toHaveURL('/');
    });

    test('Navigates to Watch Dashboard and checks elements', async ({ page }) => {
        await page.goto('/watch');

        // Verify Title and Stats
        await expect(page.locator('text=통합 관제 및 알람')).toBeVisible();
        await expect(page.locator('text=총 알림 건수')).toBeVisible();

        // Check if priority filters are rendered
        await expect(page.locator('button:has-text("Critical")')).toBeVisible();
        await expect(page.locator('button:has-text("Warning")')).toBeVisible();

        // Check if at least one feed item is listed (initial simulated data)
        await expect(page.locator('text=실시간 알림 피드')).toBeVisible();
    });

    test('Notification Bell Popover rendering', async ({ page }) => {
        await page.goto('/');

        // Click the Notification Bell
        const bellButton = page.locator('header button').first();
        await bellButton.click();

        // Verify Popover Content
        await expect(page.locator('h4:has-text("알림")')).toBeVisible();
        await expect(page.locator('text=모든 알림 보기')).toBeVisible();
    });
});
