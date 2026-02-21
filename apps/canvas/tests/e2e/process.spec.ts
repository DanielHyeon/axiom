import { test, expect } from '@playwright/test';

test.describe('Process Designer E2E', () => {
    test.beforeEach(async ({ page }) => {
        // 1. Go to Login page
        await page.goto('/login');

        // 2. Fill login form with admin role to bypass guards
        await page.fill('input[type="email"]', 'admin@axiom.ai');
        await page.fill('input[type="password"]', 'password');
        await page.click('button');

        // 3. Wait for redirect to dashboard
        await expect(page).toHaveURL('/');
    });

    test('should render the Process Designer Canvas and panels', async ({ page }) => {
        // 1. Navigate to Process Designer
        await page.goto('/process');

        // 2. Verify Toolbox
        await expect(page.getByText('도구 상자 (Toolbox)')).toBeVisible();
        await expect(page.getByText('Event')).toBeVisible();
        await expect(page.getByText('Action')).toBeVisible();

        // 3. Verify Canvas uses Konva (canvas element)
        const konvaCanvas = page.locator('canvas').first();
        await expect(konvaCanvas).toBeVisible();

        // 4. Verify Property Panel
        await expect(page.getByText('속성 패널 (Property Panel)')).toBeVisible();
        await expect(page.getByText('캔버스에서 노드를 선택하여')).toBeVisible();
    });
});
