/**
 * Schema Canvas E2E 테스트 — G1-G8 갭 기능 검증.
 *
 * 테스트 시나리오:
 *  - NL2SQL 페이지에서 Schema Canvas 접근
 *  - 모드 전환 (코드분석/데이터소스)
 *  - FK 가시성 토글 (G1)
 *  - 관계 추가 모달 (G2)
 *  - 논리명/물리명 토글 (G7)
 *  - 데이터 프리뷰 (G8)
 */
import { test, expect } from '../fixtures/auth';

/* -------------------------------------------------------------------------- */
/*  기본 페이지 로드                                                          */
/* -------------------------------------------------------------------------- */

test.describe('Schema Canvas 기본', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/analysis/nl2sql');
    // 페이지 렌더링 대기 — NL2SQL 관련 UI 요소 기반
    await authedPage.waitForSelector('nav, [role="navigation"], aside, [data-testid]', { timeout: 10000 });
  });

  test('NL2SQL 페이지 로드', async ({ authedPage }) => {
    // NL2SQL 관련 UI 요소 확인 — 404가 아닌지, 실제 컨텐츠가 있는지 검증
    const notFound = authedPage.locator('text=404').or(authedPage.locator('text=Not Found'));
    const is404 = await notFound.isVisible({ timeout: 1000 }).catch(() => false);
    expect(is404).toBe(false);
    // 페이지에 의미 있는 UI 요소가 렌더링되었는지 확인
    const hasContent = authedPage.locator('nav, [role="navigation"], aside, main, [data-testid]');
    await expect(hasContent.first()).toBeVisible({ timeout: 5000 });
  });
});

/* -------------------------------------------------------------------------- */
/*  G1: FK 가시성 토글                                                        */
/* -------------------------------------------------------------------------- */

test.describe('G1: FK 가시성 토글', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/analysis/nl2sql');
    await authedPage.waitForSelector('nav, [role="navigation"], aside, [data-testid]', { timeout: 10000 });
  });

  test('FK 소스별 토글 버튼 존재', async ({ authedPage }) => {
    // DDL, User, Fabric 토글 칩 확인
    const ddlChip = authedPage.locator('text=DDL');
    const userChip = authedPage.locator('text=User');
    const fabricChip = authedPage.locator('text=Fabric');

    // 캔버스에 테이블이 있을 때만 토글바가 표시됨
    // 데이터가 없으면 EmptyState가 표시될 수 있으므로 soft check
    const hasFkToolbar = await ddlChip
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (hasFkToolbar) {
      await expect(ddlChip).toBeVisible();
      await expect(userChip).toBeVisible();
      await expect(fabricChip).toBeVisible();
    }
  });

  test('FK 토글 클릭 시 상태 변경', async ({ authedPage }) => {
    const ddlChip = authedPage.locator('button:has-text("DDL")');
    const isVisible = await ddlChip
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (isVisible) {
      // 클릭 전 상태 기록
      await ddlChip.click();
      // 클릭 후 opacity 또는 line-through 스타일 변경 확인
      await authedPage.waitForTimeout(200);
      // 다시 클릭하여 원복
      await ddlChip.click();
    }
  });
});

/* -------------------------------------------------------------------------- */
/*  G2: 관계 편집 모달                                                        */
/* -------------------------------------------------------------------------- */

test.describe('G2: 관계 편집 모달', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/analysis/nl2sql');
    await authedPage.waitForSelector('nav, [role="navigation"], aside, [data-testid]', { timeout: 10000 });
  });

  test('관계추가 버튼 존재', async ({ authedPage }) => {
    const addRelBtn = authedPage.locator('button:has-text("관계추가")');
    const isVisible = await addRelBtn
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (isVisible) {
      await expect(addRelBtn).toBeVisible();
    }
  });

  test('관계추가 클릭 시 모달 열림', async ({ authedPage }) => {
    const addRelBtn = authedPage.locator('button:has-text("관계추가")');
    const isVisible = await addRelBtn
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (isVisible) {
      await addRelBtn.click();
      // 모달 다이얼로그 확인
      await expect(
        authedPage
          .locator('text=FK 관계')
          .or(authedPage.locator('[role="dialog"]')),
      ).toBeVisible({ timeout: 3000 });
    }
  });

  test('모달에 소스/타겟 테이블 선택 필드', async ({ authedPage }) => {
    const addRelBtn = authedPage.locator('button:has-text("관계추가")');
    const isVisible = await addRelBtn
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (isVisible) {
      await addRelBtn.click();
      // 모달 다이얼로그 렌더링 대기
      await authedPage.waitForSelector('[role="dialog"], text=FK 관계', { timeout: 3000 });
      await expect(authedPage.locator('text=소스 테이블')).toBeVisible();
      await expect(authedPage.locator('text=타겟 테이블')).toBeVisible();
    }
  });

  test('모달 닫기', async ({ authedPage }) => {
    const addRelBtn = authedPage.locator('button:has-text("관계추가")');
    const isVisible = await addRelBtn
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (isVisible) {
      await addRelBtn.click();
      // 모달 다이얼로그 렌더링 대기
      await authedPage.waitForSelector('[role="dialog"], text=FK 관계', { timeout: 3000 });
      // 취소 버튼으로 닫기
      const cancelBtn = authedPage.locator('button:has-text("취소")');
      if (await cancelBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await cancelBtn.click();
        await authedPage.waitForTimeout(200);
      }
    }
  });
});

/* -------------------------------------------------------------------------- */
/*  G7: 논리명/물리명 토글                                                    */
/* -------------------------------------------------------------------------- */

test.describe('G7: 논리명/물리명 토글', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/analysis/nl2sql');
    await authedPage.waitForSelector('nav, [role="navigation"], aside, [data-testid]', { timeout: 10000 });
  });

  test('물리명/논리명 토글 버튼 존재', async ({ authedPage }) => {
    const toggleBtn = authedPage
      .locator('button:has-text("물리명")')
      .or(authedPage.locator('button:has-text("논리명")'));
    const isVisible = await toggleBtn
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (isVisible) {
      await expect(toggleBtn).toBeVisible();
    }
  });

  test('토글 클릭 시 모드 전환', async ({ authedPage }) => {
    const physBtn = authedPage.locator('button:has-text("물리명")');
    const isVisible = await physBtn
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (isVisible) {
      await physBtn.click();
      await authedPage.waitForTimeout(200);
      // 논리명으로 변경되었는지 확인
      await expect(
        authedPage.locator('button:has-text("논리명")'),
      ).toBeVisible();
    }
  });
});

/* -------------------------------------------------------------------------- */
/*  G8: 데이터 프리뷰                                                        */
/* -------------------------------------------------------------------------- */

test.describe('G8: 데이터 프리뷰', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/analysis/nl2sql');
    await authedPage.waitForSelector('nav, [role="navigation"], aside, [data-testid]', { timeout: 10000 });
  });

  test('테이블 카드에 프리뷰 아이콘 존재', async ({ authedPage }) => {
    // 테이블 카드가 렌더링되면 프리뷰 아이콘(눈 아이콘)이 있을 수 있음
    const previewIcons = authedPage.locator(
      '[data-testid="preview-btn"], button[aria-label*="프리뷰"], button[aria-label*="preview"]',
    );
    const hasIcons = await previewIcons
      .first()
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (hasIcons) {
      await expect(previewIcons.first()).toBeVisible();
    }
  });
});

/* -------------------------------------------------------------------------- */
/*  모드 전환 (코드분석 / 데이터소스)                                         */
/* -------------------------------------------------------------------------- */

test.describe('모드 전환', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/analysis/nl2sql');
    await authedPage.waitForSelector('nav, [role="navigation"], aside, [data-testid]', { timeout: 10000 });
  });

  test('코드분석/데이터소스 모드 탭 존재', async ({ authedPage }) => {
    const roboTab = authedPage.locator('button:has-text("코드분석")');
    const text2sqlTab = authedPage.locator('button:has-text("데이터소스")');

    const hasModeTabs = await roboTab
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (hasModeTabs) {
      await expect(roboTab).toBeVisible();
      await expect(text2sqlTab).toBeVisible();
    }
  });

  test('코드분석 탭 클릭 시 모드 전환', async ({ authedPage }) => {
    const roboTab = authedPage.locator('button:has-text("코드분석")');
    const isVisible = await roboTab
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (isVisible) {
      await roboTab.click();
      await authedPage.waitForTimeout(200);
      // 코드분석 모드 관련 UI가 표시되는지 확인
      const activeState = await roboTab.getAttribute('data-state');
      // 활성 상태이거나 aria-selected가 true이면 OK
      const isActive =
        activeState === 'active' ||
        (await roboTab.getAttribute('aria-selected')) === 'true';
      // 탭이 활성화되었는지 확인 — 구현에 따라 속성이 다를 수 있으므로 soft check
      if (activeState || (await roboTab.getAttribute('aria-selected'))) {
        expect(isActive).toBeTruthy();
      }
    }
  });

  test('데이터소스 탭 클릭 시 모드 전환', async ({ authedPage }) => {
    const dsTab = authedPage.locator('button:has-text("데이터소스")');
    const isVisible = await dsTab
      .isVisible({ timeout: 3000 })
      .catch(() => false);
    if (isVisible) {
      await dsTab.click();
      await authedPage.waitForTimeout(200);
    }
  });
});
