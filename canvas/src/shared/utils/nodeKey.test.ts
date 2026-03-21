import { describe, it, expect } from 'vitest';
import { buildNodeKey, parseNodeKey } from './nodeKey';

// ---------------------------------------------------------------------------
// buildNodeKey — 노드 키 생성
// ---------------------------------------------------------------------------

describe('buildNodeKey', () => {
  it('기본 형식 — mode:datasource:schema:table 패턴으로 생성', () => {
    expect(buildNodeKey('text2sql', 'erp_db', 'public', 'orders')).toBe(
      'text2sql:erp_db:public:orders',
    );
  });

  it('빈 datasource — 빈 문자열로 처리, 빈 schema는 public 기본값', () => {
    // datasource가 빈 문자열이면 그대로, schema가 빈 문자열이면 'public'으로 대체
    expect(buildNodeKey('robo', '', '', 'users')).toBe('robo::public:users');
  });

  it('mode 타입 체크 — robo와 text2sql 모두 정상 작동', () => {
    const roboKey = buildNodeKey('robo', 'ds', 'sch', 'tbl');
    const text2sqlKey = buildNodeKey('text2sql', 'ds', 'sch', 'tbl');

    expect(roboKey).toBe('robo:ds:sch:tbl');
    expect(text2sqlKey).toBe('text2sql:ds:sch:tbl');
  });
});

// ---------------------------------------------------------------------------
// parseNodeKey — 노드 키 파싱
// ---------------------------------------------------------------------------

describe('parseNodeKey', () => {
  it('정상 파싱 — 4개 세그먼트를 올바르게 분리', () => {
    const result = parseNodeKey('text2sql:erp_db:public:orders');
    expect(result).toEqual({
      mode: 'text2sql',
      datasource: 'erp_db',
      schema: 'public',
      tableName: 'orders',
    });
  });

  it('빈 datasource — 콜론 사이에 빈 값이 있을 때 빈 문자열로 파싱', () => {
    const result = parseNodeKey('robo::public:users');
    expect(result).toEqual({
      mode: 'robo',
      datasource: '',
      schema: 'public',
      tableName: 'users',
    });
  });

  it('콜론 포함 테이블명 — 세 번째 콜론 이후 전부를 테이블명으로 처리', () => {
    const result = parseNodeKey('text2sql:db:public:my:special:table');
    expect(result).toEqual({
      mode: 'text2sql',
      datasource: 'db',
      schema: 'public',
      tableName: 'my:special:table',
    });
  });

  it('빈 입력 — 모든 필드에 안전한 기본값 반환', () => {
    const result = parseNodeKey('');
    expect(result).toEqual({
      mode: 'text2sql',
      datasource: '',
      schema: 'public',
      tableName: '',
    });
  });
});

// ---------------------------------------------------------------------------
// 라운드트립 — build → parse 왕복 검증
// ---------------------------------------------------------------------------

describe('라운드트립', () => {
  it('buildNodeKey로 생성한 키를 parseNodeKey로 파싱하면 원래 값 복원', () => {
    const original = {
      mode: 'text2sql' as const,
      datasource: 'erp',
      schema: 'sales',
      tableName: 'invoices',
    };

    const key = buildNodeKey(
      original.mode,
      original.datasource,
      original.schema,
      original.tableName,
    );
    const parsed = parseNodeKey(key);

    expect(parsed.mode).toBe(original.mode);
    expect(parsed.datasource).toBe(original.datasource);
    expect(parsed.schema).toBe(original.schema);
    expect(parsed.tableName).toBe(original.tableName);
  });

  it('robo 모드로도 라운드트립 정상 동작', () => {
    const key = buildNodeKey('robo', 'code_repo', 'dbo', 'user_accounts');
    const parsed = parseNodeKey(key);

    expect(parsed.mode).toBe('robo');
    expect(parsed.datasource).toBe('code_repo');
    expect(parsed.schema).toBe('dbo');
    expect(parsed.tableName).toBe('user_accounts');
  });
});

// ---------------------------------------------------------------------------
// 추가 엣지 케이스 — 경계값 및 특수 상황 검증
// ---------------------------------------------------------------------------

describe('buildNodeKey 엣지 케이스', () => {
  it('schema가 빈 문자열이면 public 기본값으로 대체', () => {
    expect(buildNodeKey('text2sql', 'db', '', 'tbl')).toBe('text2sql:db:public:tbl');
  });

  it('datasource가 빈 문자열이면 빈 상태 유지', () => {
    expect(buildNodeKey('text2sql', '', 'myschema', 'tbl')).toBe('text2sql::myschema:tbl');
  });

  it('특수문자가 포함된 테이블명도 그대로 포함', () => {
    expect(buildNodeKey('text2sql', 'db', 'public', 'my-table_v2')).toBe(
      'text2sql:db:public:my-table_v2',
    );
  });
});

describe('parseNodeKey 엣지 케이스', () => {
  it('세그먼트가 부족한 경우 — 기본값으로 채움', () => {
    const result = parseNodeKey('text2sql');
    expect(result).toEqual({
      mode: 'text2sql',
      datasource: '',
      schema: 'public',
      tableName: '',
    });
  });

  it('세그먼트가 2개만 있는 경우', () => {
    const result = parseNodeKey('robo:mydb');
    expect(result).toEqual({
      mode: 'robo',
      datasource: 'mydb',
      schema: 'public',
      tableName: '',
    });
  });

  it('세그먼트가 3개만 있는 경우 — 테이블명 빈 문자열', () => {
    const result = parseNodeKey('text2sql:db:schema');
    expect(result).toEqual({
      mode: 'text2sql',
      datasource: 'db',
      schema: 'schema',
      tableName: '',
    });
  });

  it('알 수 없는 mode 값도 그대로 반환', () => {
    const result = parseNodeKey('unknown:db:public:tbl');
    expect(result.mode).toBe('unknown');
  });
});
