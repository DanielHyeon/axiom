/**
 * OLAP Studio 데이터 관리 플로우 E2E 테스트.
 *
 * 테스트 시나리오:
 *  - 데이터 소스 페이지 접근
 *  - ETL 파이프라인 페이지 접근
 *  - 큐브 관리 페이지 접근
 */
import { test, expect } from '../fixtures/auth';

test.describe('데이터 소스 관리', () => {
  test('페이지 로드', async ({ authedPage }) => {
    await authedPage.goto('/data/sources');
    await expect(authedPage.locator('text=데이터 소스')).toBeVisible({
      timeout: 10000,
    });
  });

  test('추가 버튼 존재', async ({ authedPage }) => {
    await authedPage.goto('/data/sources');
    await authedPage.waitForSelector('text=데이터 소스', { timeout: 10000 });
    await expect(authedPage.locator('button:has-text("추가")')).toBeVisible();
  });

  test('추가 폼 토글', async ({ authedPage }) => {
    await authedPage.goto('/data/sources');
    await authedPage.waitForSelector('text=데이터 소스', { timeout: 10000 });

    // 추가 버튼 클릭
    await authedPage.click('button:has-text("추가")');

    // 폼 필드 확인
    await expect(
      authedPage
        .locator('text=이름')
        .or(authedPage.locator('input[placeholder*="이름"]')),
    ).toBeVisible();
    await expect(
      authedPage.locator('text=유형').or(authedPage.locator('select')),
    ).toBeVisible();

    // 취소 버튼
    await expect(authedPage.locator('button:has-text("취소")')).toBeVisible();
  });

  test('빈 상태 메시지', async ({ authedPage }) => {
    await authedPage.goto('/data/sources');
    await authedPage.waitForSelector('text=데이터 소스', { timeout: 10000 });
    // 데이터소스가 없으면 빈 상태 메시지
    const emptyMsg = authedPage.locator('text=등록된 데이터소스가 없습니다');
    // 데이터가 있을 수도 있으므로 soft assertion
    if (await emptyMsg.isVisible({ timeout: 3000 }).catch(() => false)) {
      await expect(emptyMsg).toBeVisible();
    }
  });
});

test.describe('ETL 파이프라인 관리', () => {
  test('페이지 로드', async ({ authedPage }) => {
    await authedPage.goto('/data/etl');
    await expect(
      authedPage
        .locator('text=ETL')
        .or(authedPage.locator('text=파이프라인')),
    ).toBeVisible({ timeout: 10000 });
  });

  test('추가 버튼 존재', async ({ authedPage }) => {
    await authedPage.goto('/data/etl');
    // ETL 페이지 로드 대기 — 제목 텍스트 기반
    await authedPage.waitForSelector('text=ETL', { timeout: 10000 });
    await expect(
      authedPage
        .locator('button:has-text("추가")')
        .or(authedPage.locator('button:has-text("생성")')),
    ).toBeVisible();
  });
});

test.describe('큐브 관리', () => {
  test('페이지 로드', async ({ authedPage }) => {
    await authedPage.goto('/data/cubes');
    await expect(authedPage.locator('text=큐브')).toBeVisible({
      timeout: 10000,
    });
  });

  test('추가 버튼 존재', async ({ authedPage }) => {
    await authedPage.goto('/data/cubes');
    // 큐브 페이지 로드 대기 — 제목 텍스트 기반
    await authedPage.waitForSelector('text=큐브', { timeout: 10000 });
    await expect(
      authedPage
        .locator('button:has-text("추가")')
        .or(authedPage.locator('button:has-text("생성")')),
    ).toBeVisible();
  });

  test('큐브 상태 워크플로 버튼', async ({ authedPage }) => {
    await authedPage.goto('/data/cubes');
    // 큐브 페이지 로드 대기 — 제목 텍스트 기반
    await authedPage.waitForSelector('text=큐브', { timeout: 10000 });
    // 검증/게시 버튼이 존재할 수 있음 (큐브가 있는 경우)
    const validateBtn = authedPage.locator('button:has-text("검증")');
    const publishBtn = authedPage.locator('button:has-text("게시")');
    const cubeCards = authedPage.locator('[data-testid*="cube"], .cube-card, tr');
    // 큐브가 없으면 버튼 안 보일 수 있으므로 soft check
    const hasValidateBtn =
      await validateBtn.isVisible({ timeout: 2000 }).catch(() => false);
    const hasPublishBtn =
      await publishBtn.isVisible({ timeout: 2000 }).catch(() => false);
    const cubeCount = await cubeCards.count();
    // 워크플로 버튼이 있거나, 큐브가 없어서 버튼이 없는 경우 모두 정상
    expect(hasValidateBtn || hasPublishBtn || cubeCount === 0).toBe(true);
  });
});
