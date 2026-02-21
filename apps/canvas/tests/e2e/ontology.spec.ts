import { test, expect } from '@playwright/test';

test.describe('Sprint 6 - Ontology Browser UI Validation', () => {

    test.beforeEach(async ({ page }) => {
        // Authenticate as an admin role
        await page.goto('/login');
        await page.fill('input[type="email"]', 'admin@axiom.ai');
        await page.fill('input[type="password"]', 'password');
        await page.click('button');
        await expect(page).toHaveURL('/');
    });

    test('Loads Ontology Canvas and Renders Nodes', async ({ page }) => {
        await page.goto('/ontology');

        // Check Header rendering
        await expect(page.locator('text=K-AIR 온톨로지 탐색')).toBeVisible();

        // Check if the graph viewer canvas is mounted
        const graphCanvas = page.locator('canvas').first();
        await expect(graphCanvas).toBeVisible();

        // Check if the Node Detail default empty state is visible
        await expect(page.locator('text=상세 정보가 표시됩니다.')).toBeVisible();

        // Ensure filters are present
        await expect(page.locator('text=계층:')).toBeVisible();
    });
});
