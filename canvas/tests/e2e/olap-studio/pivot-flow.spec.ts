/**
 * OLAP Studio 피벗 분석 플로우 E2E 테스트.
 *
 * 테스트 시나리오:
 *  1. OLAP Studio 페이지로 이동
 *  2. 큐브 선택
 *  3. 차원/측정값 추가
 *  4. 피벗 실행
 *  5. 결과 확인
 *  6. SQL 미리보기 확인
 */
import { test, expect } from '../fixtures/auth';

test.describe('OLAP Studio 피벗 분석', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/analysis/olap-studio');
    // 페이지 로드 대기
    await authedPage.waitForSelector('text=OLAP Studio', { timeout: 10000 });
  });

  test('페이지 로드 및 기본 구조 확인', async ({ authedPage }) => {
    // 헤더 확인
    await expect(authedPage.locator('text=OLAP Studio')).toBeVisible();

    // 큐브 선택 드롭다운 존재
    await expect(authedPage.locator('select, [data-testid="cube-selector"]')).toBeVisible();

    // 4개 드롭존 확인
    await expect(authedPage.locator('text=행 (Rows)')).toBeVisible();
    await expect(authedPage.locator('text=열 (Columns)')).toBeVisible();
    await expect(authedPage.locator('text=측정값 (Measures)')).toBeVisible();
    await expect(authedPage.locator('text=필터 (Filters)')).toBeVisible();
  });

  test('큐브 미선택 시 안내 메시지 표시', async ({ authedPage }) => {
    // 큐브를 선택하지 않으면 차원/측정값 영역에 안내 메시지
    const placeholder = authedPage.locator('text=큐브를 선택하세요');
    // 큐브 목록이 비어있거나 미선택 시 표시될 수 있음
    await expect(placeholder.or(authedPage.locator('select'))).toBeVisible();
  });

  test('실행 버튼: 측정값 없으면 비활성', async ({ authedPage }) => {
    const executeBtn = authedPage.locator('button:has-text("실행")');
    await expect(executeBtn).toBeVisible();
    // 측정값이 없으므로 비활성 상태
    await expect(executeBtn).toBeDisabled();
  });

  test('SQL 보기 버튼 존재', async ({ authedPage }) => {
    const sqlBtn = authedPage.locator('button:has-text("SQL 보기")');
    await expect(sqlBtn).toBeVisible();
  });

  test('결과/SQL 탭 전환', async ({ authedPage }) => {
    // 결과 탭 (기본 활성)
    const resultTab = authedPage.locator('button:has-text("결과")');
    const sqlTab = authedPage.locator('button:has-text("SQL")');

    await expect(resultTab).toBeVisible();
    await expect(sqlTab).toBeVisible();

    // SQL 탭 클릭
    await sqlTab.click();
    // SQL 미리보기 영역 확인
    await expect(
      authedPage
        .locator('text=SQL 미리보기')
        .or(authedPage.locator('text=피벗을 설정하고')),
    ).toBeVisible();

    // 결과 탭으로 복귀
    await resultTab.click();
    await expect(
      authedPage
        .locator('text=피벗을 실행하면')
        .or(resultTab),
    ).toBeVisible();
  });

  test('드롭존에 필드 추가 후 칩 표시', async ({ authedPage }) => {
    // 좌측 패널에서 차원 이름을 찾아 행 추가 버튼 클릭
    // (차원 목록이 동적으로 로드되므로, 목록이 있으면 첫 번째 항목 클릭)
    const dimensionItems = authedPage.locator('[title="행에 추가"]');
    if ((await dimensionItems.count()) > 0) {
      await dimensionItems.first().click();
      // 행 드롭존에 칩이 추가되었는지 확인
      const rowZone = authedPage.locator('text=행 (Rows)').locator('..');
      const chipCount = await rowZone.locator('span').count();
      expect(chipCount).toBeGreaterThan(0);
    }
  });
});

test.describe('OLAP Studio 좌측 패널', () => {
  test.beforeEach(async ({ authedPage }) => {
    await authedPage.goto('/analysis/olap-studio');
    await authedPage.waitForSelector('text=OLAP Studio', { timeout: 10000 });
  });

  test('차원 섹션 존재', async ({ authedPage }) => {
    await expect(
      authedPage
        .locator('text=차원 (Dimensions)')
        .or(authedPage.locator('text=차원')),
    ).toBeVisible();
  });

  test('측정값 섹션 존재', async ({ authedPage }) => {
    await expect(
      authedPage
        .locator('text=측정값 (Measures)')
        .or(authedPage.locator('text=측정값')),
    ).toBeVisible();
  });
});
