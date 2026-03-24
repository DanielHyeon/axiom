/**
 * E2E 테스트용 API 모킹 헬퍼.
 *
 * 각 마이크로서비스의 API 엔드포인트를 기본 성공 응답으로 모킹한다.
 * 개별 테스트에서 특정 엔드포인트만 오버라이드하여 사용할 수 있다.
 */
import type { Page } from '@playwright/test';

/** 기본 인증 사용자 mock 데이터 */
const MOCK_AUTH_USER = {
  id: '1',
  email: 'test@axiom.io',
  role: 'admin',
  tenantId: 'T-001',
  name: 'Test Admin',
};

/**
 * 모든 주요 API 라우트를 기본 성공 응답으로 모킹한다.
 * 테스트 시작 시 page.goto() 호출 전에 사용해야 한다.
 */
export async function mockAllApiRoutes(page: Page) {
  // Core (9002) — 인증/인가
  await page.route('**/api/v1/auth/**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: { user: MOCK_AUTH_USER },
      },
    }),
  );

  // Synapse (9003) — 시멘틱 카탈로그, 온톨로지
  await page.route('**/api/v3/synapse/**', (route) =>
    route.fulfill({
      json: { success: true, data: [] },
    }),
  );

  // Weaver (9001) — 품질, 메타데이터
  await page.route('**/api/v1/weaver/**', (route) =>
    route.fulfill({
      json: { success: true, data: {} },
    }),
  );

  // Oracle (9004) — NL2SQL
  await page.route('**/api/v1/oracle/**', (route) =>
    route.fulfill({
      json: { success: true, data: {} },
    }),
  );

  // Vision (9100) — OLAP, What-if
  await page.route('**/api/v1/vision/**', (route) =>
    route.fulfill({
      json: { success: true, data: {} },
    }),
  );

  // OLAP Studio (9005)
  await page.route('**/api/v1/olap-studio/**', (route) =>
    route.fulfill({
      json: { success: true, data: {} },
    }),
  );
}

/**
 * 시멘틱 카탈로그 관련 API 를 상세 mock 데이터와 함께 모킹한다.
 * 11탭 브라우징 테스트에 사용된다.
 */
export async function mockSemanticCatalogApis(page: Page) {
  // 온톨로지 개념 목록
  await page.route('**/api/v3/synapse/semantic/concepts**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { id: 'c-1', name: 'OEE', layer: 'kpi', status: 'approved', description: '설비종합효율' },
          { id: 'c-2', name: 'Throughput', layer: 'kpi', status: 'approved', description: '처리량' },
        ],
      },
    }),
  );

  // 시멘틱 엔티티 목록
  await page.route('**/api/v3/synapse/semantic/entities**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { id: 'e-1', name: 'fact_production', description: '생산 실적', status: 'published' },
          { id: 'e-2', name: 'dim_product', description: '제품 마스터', status: 'published' },
        ],
      },
    }),
  );

  // 지표 목록
  await page.route('**/api/v3/synapse/semantic/measures**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { id: 'm-1', entity_id: 'e-1', name: 'total_output', measure_type: 'sum', sql_expression: 'SUM(output_qty)' },
        ],
      },
    }),
  );

  // 차원 목록
  await page.route('**/api/v3/synapse/semantic/dimensions**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { id: 'd-1', entity_id: 'e-2', name: 'product_name', value_type: 'string' },
        ],
      },
    }),
  );

  // 조인 계약
  await page.route('**/api/v3/synapse/semantic/joins**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { id: 'j-1', left_entity_id: 'e-1', right_entity_id: 'e-2', join_condition: 'product_id = product_id' },
        ],
      },
    }),
  );

  // 그레인 계약
  await page.route('**/api/v3/synapse/semantic/grains**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { id: 'g-1', entity_id: 'e-1', grain_key_set: ['product_id', 'date'], time_grain: 'day' },
        ],
      },
    }),
  );

  // 스냅샷 (런타임)
  await page.route('**/api/v3/synapse/semantic/snapshots**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { id: 's-1', version: '1.0.0', status: 'active', created_at: '2026-03-20T00:00:00Z' },
        ],
      },
    }),
  );

  // 온톨로지 관계
  await page.route('**/api/v3/synapse/semantic/relations**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { id: 'r-1', subject_id: 'c-1', predicate: 'DERIVED_FROM', object_id: 'c-2' },
        ],
      },
    }),
  );

  // 규칙/정책
  await page.route('**/api/v3/synapse/semantic/rules**', (route) =>
    route.fulfill({
      json: { success: true, data: [] },
    }),
  );
  await page.route('**/api/v3/synapse/semantic/policies**', (route) =>
    route.fulfill({
      json: { success: true, data: [] },
    }),
  );

  // 별칭 그룹
  await page.route('**/api/v3/synapse/semantic/alias-groups**', (route) =>
    route.fulfill({
      json: { success: true, data: [] },
    }),
  );

  // 세그먼트, 시간 계약, 접근 정책 (L2 확장)
  await page.route('**/api/v3/synapse/semantic/segments**', (route) =>
    route.fulfill({
      json: { success: true, data: [] },
    }),
  );
  await page.route('**/api/v3/synapse/semantic/time-contracts**', (route) =>
    route.fulfill({
      json: { success: true, data: [] },
    }),
  );
  await page.route('**/api/v3/synapse/semantic/access-policies**', (route) =>
    route.fulfill({
      json: { success: true, data: [] },
    }),
  );
}

/**
 * 품질 대시보드 API 를 mock 데이터와 함께 모킹한다.
 */
export async function mockQualityDashboardApis(page: Page) {
  // 품질 대시보드 요약
  await page.route('**/api/v1/weaver/quality/dashboard**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          total_tables: 42,
          avg_score: 78.5,
          trusted_count: 20,
          caution_count: 15,
          reference_only_count: 5,
          blocked_count: 2,
        },
      },
    }),
  );

  // 품질 점수 목록
  await page.route('**/api/v1/weaver/quality/scores**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          {
            table_name: 'fact_production',
            overall_score: 92.3,
            trust_grade: 'TRUSTED',
            freshness: 95,
            completeness: 90,
            validity: 88,
            uniqueness: 100,
          },
          {
            table_name: 'dim_product',
            overall_score: 65.1,
            trust_grade: 'CAUTION',
            freshness: 60,
            completeness: 70,
            validity: 75,
            uniqueness: 55,
          },
          {
            table_name: 'stg_raw_logs',
            overall_score: 35.0,
            trust_grade: 'REFERENCE_ONLY',
            freshness: 20,
            completeness: 40,
            validity: 50,
            uniqueness: 30,
          },
        ],
      },
    }),
  );

  // 품질 이력
  await page.route('**/api/v1/weaver/quality/history**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          { date: '2026-03-20', avg_score: 76.2 },
          { date: '2026-03-21', avg_score: 77.1 },
          { date: '2026-03-22', avg_score: 78.5 },
        ],
      },
    }),
  );

  // breach 목록
  await page.route('**/api/v1/weaver/quality/breaches**', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: [
          {
            id: 'b-1',
            table_name: 'stg_raw_logs',
            dimension: 'freshness',
            threshold: 70,
            actual: 20,
            created_at: '2026-03-22T10:30:00Z',
          },
        ],
      },
    }),
  );
}
