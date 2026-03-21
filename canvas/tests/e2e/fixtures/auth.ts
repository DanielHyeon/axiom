/**
 * E2E 테스트 인증 픽스처.
 *
 * 테스트 전 로그인을 처리하고 인증된 페이지 컨텍스트를 제공한다.
 * 기본 계정: admin@local.axiom / admin (SEED_DEV_USER=1)
 */
import { test as base, type Page } from '@playwright/test';

// 기본 개발 계정
const DEV_USER = {
  email: 'admin@local.axiom',
  password: 'admin',
};

export type AuthFixtures = {
  /** 인증된 페이지 */
  authedPage: Page;
};

export const test = base.extend<AuthFixtures>({
  authedPage: async ({ page }, use) => {
    // 로그인 페이지로 이동
    await page.goto('/auth/login');

    // 로그인 폼이 없으면 (이미 인증됨) 바로 사용
    const loginForm = page.locator('form, [data-testid="login-form"]');
    if (await loginForm.isVisible({ timeout: 3000 }).catch(() => false)) {
      // 이메일/패스워드 입력
      await page.fill('input[type="email"], input[name="email"]', DEV_USER.email);
      await page.fill('input[type="password"], input[name="password"]', DEV_USER.password);
      await page.click('button[type="submit"]');

      // 대시보드로 이동될 때까지 대기
      await page.waitForURL(/\/(dashboard|analysis|data)/, { timeout: 10000 });
    }

    // JWT 토큰이 localStorage에 저장되었는지 확인
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    if (!token) {
      // 토큰이 없으면 mock 토큰 주입 (개발 환경)
      await page.evaluate(() => {
        localStorage.setItem('access_token', 'dev-mock-token');
        localStorage.setItem('tenant_id', '00000000-0000-0000-0000-000000000001');
      });
    }

    await use(page);
  },
});

export { expect } from '@playwright/test';
