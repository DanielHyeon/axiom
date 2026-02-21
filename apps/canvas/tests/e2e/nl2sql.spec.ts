import { test, expect } from '@playwright/test';

test.describe('NL2SQL E2E', () => {
    // Use existing setup or direct URL bypass since auth is mocked in previous tests
    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        // 2. Fill login form with admin role to bypass guards
        await page.fill('input[type="email"]', 'admin@axiom.ai');
        await page.fill('input[type="password"]', 'password');
        await page.click('button');

        // 3. Wait for redirect to dashboard
        await expect(page).toHaveURL('/');
    });

    test('should render NL2SQL chat interface and execute a mock query', async ({ page }) => {
        // 1. Navigate to NL2SQL page
        await page.goto('/nl2sql');
        await expect(page).toHaveURL(/.*\/nl2sql/);

        // 2. Verify layout
        await expect(page.locator('h2').filter({ hasText: 'NL2SQL' })).toBeVisible();
        await expect(page.getByPlaceholder('데이터에 대해 질문해 보세요... (Enter로 전송)')).toBeVisible();

        // 3. Verify Empty State Suggestions
        await expect(page.getByText('무엇을 도와드릴까요?')).toBeVisible();

        // 4. Type a query manually instead of clicking the suggestion (to avoid flaky text matching)
        await page.fill('input[placeholder="데이터에 대해 질문해 보세요... (Enter로 전송)"]', '지난 분기 부채비율 상위 10개 기업은?');
        await page.keyboard.press('Enter');

        // 5. Verify the AI is "Thinking"
        await expect(page.locator('text=질문을 분석하고 있습니다...')).toBeVisible({ timeout: 5000 });

        // 6. Verify the SQL Preview appears
        await expect(page.locator('text=SELECT company_name')).toBeVisible({ timeout: 8000 });

        // 7. Verify the Final Result appears (Table and Chart)
        await expect(page.getByText('데이터 테이블')).toBeVisible({ timeout: 8000 });

        // 8. Verify Table Data (first row mock data)
        await expect(page.getByRole('cell', { name: '(주)한진' }).first()).toBeVisible();

        // 9. Verify Chart Label
        await expect(page.getByText('AI 추천 차트: 막대 차트')).toBeVisible();
    });
});
