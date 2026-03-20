import { describe, it, expect } from 'vitest';
import {
  parseFingerprint,
  getFingerprintFromParams,
  buildFingerprintUrl,
  fingerprintToDisplayName,
} from './fingerprintUtils';

// ---------------------------------------------------------------------------
// parseFingerprint
// ---------------------------------------------------------------------------

describe('parseFingerprint', () => {
  it('일반 문자열 → 그대로 반환 (trim 적용)', () => {
    expect(parseFingerprint('  oee_total  ')).toBe('oee_total');
  });

  it('URL 인코딩된 문자열 → 디코딩', () => {
    expect(parseFingerprint('hello%20world')).toBe('hello world');
  });

  it('잘못된 인코딩 → 원본 trim 반환 (에러 미발생)', () => {
    // %ZZ는 유효하지 않은 percent-encoding
    expect(parseFingerprint('%ZZ')).toBe('%ZZ');
  });

  it('빈 문자열 → 빈 문자열', () => {
    expect(parseFingerprint('')).toBe('');
  });

  it('한국어 인코딩 → 디코딩', () => {
    const encoded = encodeURIComponent('생산성지표');
    expect(parseFingerprint(encoded)).toBe('생산성지표');
  });
});

// ---------------------------------------------------------------------------
// getFingerprintFromParams
// ---------------------------------------------------------------------------

describe('getFingerprintFromParams', () => {
  it('fp 파라미터가 있으면 파싱된 값 반환', () => {
    const params = new URLSearchParams('fp=oee_total');
    expect(getFingerprintFromParams(params)).toBe('oee_total');
  });

  it('fp 파라미터가 없으면 null 반환', () => {
    const params = new URLSearchParams('other=value');
    expect(getFingerprintFromParams(params)).toBeNull();
  });

  it('fp 파라미터가 빈 문자열이면 null 반환', () => {
    // URLSearchParams('fp=')는 빈 문자열 — get()은 '' 반환 → falsy → null
    const params = new URLSearchParams('fp=');
    expect(getFingerprintFromParams(params)).toBeNull();
  });

  it('URL 인코딩된 fp 값을 디코딩', () => {
    const params = new URLSearchParams('fp=hello%20world');
    expect(getFingerprintFromParams(params)).toBe('hello world');
  });
});

// ---------------------------------------------------------------------------
// buildFingerprintUrl
// ---------------------------------------------------------------------------

describe('buildFingerprintUrl', () => {
  it('basePath + fingerprint → 올바른 URL 생성', () => {
    const url = buildFingerprintUrl('/analysis/insight', 'oee_total');
    expect(url).toBe('/analysis/insight?fp=oee_total');
  });

  it('특수문자 포함 fingerprint → URL 인코딩', () => {
    const url = buildFingerprintUrl('/insight', 'hello world');
    expect(url).toBe('/insight?fp=hello%20world');
  });

  it('동일 입력 → 동일 URL (결정적)', () => {
    const url1 = buildFingerprintUrl('/a', 'test');
    const url2 = buildFingerprintUrl('/a', 'test');
    expect(url1).toBe(url2);
  });

  it('다른 입력 → 다른 URL', () => {
    const url1 = buildFingerprintUrl('/a', 'fp1');
    const url2 = buildFingerprintUrl('/a', 'fp2');
    expect(url1).not.toBe(url2);
  });
});

// ---------------------------------------------------------------------------
// fingerprintToDisplayName
// ---------------------------------------------------------------------------

describe('fingerprintToDisplayName', () => {
  it('언더스코어 → 공백 + 단어 첫 글자 대문자', () => {
    expect(fingerprintToDisplayName('orders_pending_count')).toBe(
      'Orders Pending Count',
    );
  });

  it('단일 단어 → 첫 글자 대문자', () => {
    expect(fingerprintToDisplayName('throughput')).toBe('Throughput');
  });

  it('sha256: 접두사가 있는 해시 → 그대로 반환', () => {
    const hash = 'sha256:abc123def456';
    expect(fingerprintToDisplayName(hash)).toBe(hash);
  });

  it('빈 문자열 → 빈 문자열', () => {
    expect(fingerprintToDisplayName('')).toBe('');
  });
});
