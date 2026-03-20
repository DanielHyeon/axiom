import { test, expect } from '@playwright/test';

test.describe('Document Management E2E', () => {
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

    test('should view document list and open document editor', async ({ page }) => {
        // 1. Navigate to Documents
        await page.goto('/documents');
        await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible();

        // 2. Check if mock document exists in DataTable
        const docRow = page.locator('tr', { hasText: '이해관계자목록v3' });
        await expect(docRow).toBeVisible();

        // 3. Click the document to open editor
        await docRow.click();
        await expect(page).toHaveURL(/.*\/documents\/doc-1/);

        // 4. Verify Editor and Review Panel are visible
        // The Monaco editor injects a wrapper with 'monaco-editor' class
        await expect(page.locator('.monaco-editor').first()).toBeVisible();

        // Check Review panel
        await expect(page.getByText('리뷰 패널')).toBeVisible();
        await expect(page.getByText('운영팀 예산 확인 필요합니다. 12억이 맞는지?')).toBeVisible();
    });
});
