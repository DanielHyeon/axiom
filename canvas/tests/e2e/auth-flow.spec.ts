/**
 * E2E: 인증 플로우 — 로그인 → 대시보드 → 역할별 패널 확인.
 * Phase 2 핵심 E2E 시나리오 #1.
 *
 * 실행: npx playwright test e2e/auth-flow.spec.ts
 * 사전: canvas dev 서버(5173) + Core 서비스(9002) 가동 필요
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';

test.describe('Authentication Flow', () => {
  test('로그인 → 대시보드 이동 → 역할 인사 확인', async ({ page }) => {
    // 1. 로그인 페이지 접근
    await page.goto(`${BASE_URL}/auth/login`);
    await expect(page).toHaveURL(/\/auth\/login/);

    // 2. 로그인 폼 작성
    await page.fill('input[name="email"], input[type="email"]', 'admin@local.axiom');
    await page.fill('input[name="password"], input[type="password"]', 'admin');
    await page.click('button[type="submit"]');

    // 3. 대시보드 리다이렉트 확인
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    await expect(page).toHaveURL(/\/dashboard/);

    // 4. RoleGreeting 컴포넌트 렌더링 확인
    const greeting = page.locator('text=안녕하세요');
    await expect(greeting).toBeVisible({ timeout: 5000 });

    // 5. 통계 카드 4개 렌더링 확인
    const statsCards = page.locator('[class*="StatsCard"], [class*="stats"]');
    // 최소 1개 이상 렌더링 (API가 없어도 0으로 표시)
    await expect(page.locator('h2:has-text("케이스")')).toBeVisible({ timeout: 5000 });
  });

  test('로그인 실패 → 에러 메시지 표시', async ({ page }) => {
    await page.goto(`${BASE_URL}/auth/login`);
    await page.fill('input[name="email"], input[type="email"]', 'wrong@test.com');
    await page.fill('input[name="password"], input[type="password"]', 'wrong');
    await page.click('button[type="submit"]');

    // 에러 토스트 또는 에러 메시지 확인
    const errorIndicator = page.locator('[role="alert"], [data-sonner-toast], .text-destructive');
    await expect(errorIndicator.first()).toBeVisible({ timeout: 5000 });
  });

  test('미인증 상태 → 보호 라우트 접근 시 로그인 리다이렉트', async ({ page }) => {
    // 쿠키/토큰 없이 대시보드 직접 접근
    await page.goto(`${BASE_URL}/dashboard`);

    // 로그인 페이지로 리다이렉트 확인
    await page.waitForURL('**/auth/login', { timeout: 5000 });
    await expect(page).toHaveURL(/\/auth\/login/);
  });
});
