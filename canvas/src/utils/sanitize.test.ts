/**
 * sanitize 유틸 테스트 -- 3단계 입력 방어 전략 검증.
 *
 * 1단계: sanitizeText (HTML 이스케이프 + 길이 제한)
 * 2단계: stripHtmlTags (태그 제거 + allowlist)
 * 3단계: sanitizeUrl / sanitizeFilename / isValidIdentifier
 */
import { describe, it, expect } from 'vitest';
import {
  sanitizeText,
  stripHtmlTags,
  sanitizeUrl,
  sanitizeFilename,
  isValidIdentifier,
} from './sanitize';

// ── 1단계: sanitizeText ──

describe('sanitizeText', () => {
  it('빈 문자열을 그대로 반환한다', () => {
    expect(sanitizeText('')).toBe('');
  });

  it('일반 텍스트를 그대로 반환한다', () => {
    expect(sanitizeText('Hello World')).toBe('Hello World');
  });

  it('HTML 특수 문자를 이스케이프한다', () => {
    expect(sanitizeText('<script>alert("xss")</script>')).toBe(
      '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;',
    );
  });

  it('작은따옴표를 이스케이프한다', () => {
    expect(sanitizeText("it's")).toBe('it&#x27;s');
  });

  it('앰퍼샌드를 이스케이프한다', () => {
    expect(sanitizeText('a & b')).toBe('a &amp; b');
  });

  it('maxLength를 초과하면 잘라낸다', () => {
    const long = 'a'.repeat(2000);
    const result = sanitizeText(long, 100);
    // 이스케이프할 문자가 없으므로 길이가 정확히 100
    expect(result.length).toBe(100);
  });

  it('기본 maxLength(1000)를 적용한다', () => {
    const long = 'b'.repeat(1500);
    expect(sanitizeText(long).length).toBe(1000);
  });

  it('유니코드 문자열을 정상 처리한다', () => {
    expect(sanitizeText('한글 테스트 🎉')).toBe('한글 테스트 🎉');
  });

  it('XSS 이벤트 핸들러 페이로드를 이스케이프한다', () => {
    const payload = '<img src=x onerror=alert(1)>';
    const result = sanitizeText(payload);
    expect(result).not.toContain('<img');
    expect(result).toContain('&lt;img');
  });

  it('여러 특수 문자가 혼합된 입력을 처리한다', () => {
    expect(sanitizeText('a < b & c > "d" \'e\'')).toBe(
      'a &lt; b &amp; c &gt; &quot;d&quot; &#x27;e&#x27;',
    );
  });
});

// ── 2단계: stripHtmlTags ──

describe('stripHtmlTags', () => {
  it('빈 문자열을 그대로 반환한다', () => {
    expect(stripHtmlTags('')).toBe('');
  });

  it('모든 태그를 제거한다 (allowedTags 없을 때)', () => {
    expect(stripHtmlTags('<p>Hello</p> <b>World</b>')).toBe('Hello World');
  });

  it('allowedTags에 포함된 태그는 유지한다', () => {
    const result = stripHtmlTags('<b>bold</b> <script>evil</script>', ['b']);
    expect(result).toBe('<b>bold</b> evil');
  });

  it('script 태그를 제거한다', () => {
    expect(stripHtmlTags('<script>alert(1)</script>safe')).toBe('alert(1)safe');
  });

  it('중첩 태그를 처리한다', () => {
    expect(stripHtmlTags('<div><p>text</p></div>')).toBe('text');
  });

  it('자기 닫기(self-closing) 태그를 제거한다', () => {
    expect(stripHtmlTags('before<br/>after')).toBe('beforeafter');
  });

  it('대소문자를 무시하고 allowedTags를 적용한다', () => {
    const result = stripHtmlTags('<B>bold</B> <I>italic</I>', ['b']);
    expect(result).toBe('<B>bold</B> italic');
  });

  it('태그가 없는 텍스트를 그대로 반환한다', () => {
    expect(stripHtmlTags('no tags here')).toBe('no tags here');
  });
});

// ── 3단계: sanitizeUrl ──

describe('sanitizeUrl', () => {
  it('유효한 http URL을 허용한다', () => {
    expect(sanitizeUrl('http://example.com')).toBe('http://example.com/');
  });

  it('유효한 https URL을 허용한다', () => {
    expect(sanitizeUrl('https://example.com/path?q=1')).toBe(
      'https://example.com/path?q=1',
    );
  });

  it('javascript: 프로토콜을 차단한다', () => {
    expect(sanitizeUrl('javascript:alert(1)')).toBe('');
  });

  it('data: 프로토콜을 차단한다', () => {
    expect(sanitizeUrl('data:text/html,<script>alert(1)</script>')).toBe('');
  });

  it('ftp: 프로토콜을 차단한다', () => {
    expect(sanitizeUrl('ftp://files.example.com')).toBe('');
  });

  it('잘못된 URL을 빈 문자열로 반환한다', () => {
    expect(sanitizeUrl('not a url')).toBe('');
  });

  it('빈 문자열을 빈 문자열로 반환한다', () => {
    expect(sanitizeUrl('')).toBe('');
  });
});

// ── 3단계: sanitizeFilename ──

describe('sanitizeFilename', () => {
  it('정상 파일명을 그대로 반환한다', () => {
    expect(sanitizeFilename('report.pdf')).toBe('report.pdf');
  });

  it('경로 순회 시퀀스(..)를 밑줄로 치환한다', () => {
    expect(sanitizeFilename('../../etc/passwd')).toBe('____etc_passwd');
  });

  it('슬래시와 백슬래시를 밑줄로 치환한다', () => {
    expect(sanitizeFilename('path/to\\file')).toBe('path_to_file');
  });

  it('Windows 금지 문자를 밑줄로 치환한다', () => {
    expect(sanitizeFilename('file:name*?.txt')).toBe('file_name__.txt');
  });

  it('maxLength를 초과하면 잘라낸다', () => {
    const long = 'x'.repeat(300);
    expect(sanitizeFilename(long, 100).length).toBe(100);
  });

  it('빈 문자열을 그대로 반환한다', () => {
    expect(sanitizeFilename('')).toBe('');
  });

  it('유니코드 파일명을 허용한다', () => {
    expect(sanitizeFilename('보고서_2026.xlsx')).toBe('보고서_2026.xlsx');
  });
});

// ── 3단계: isValidIdentifier ──

describe('isValidIdentifier', () => {
  it('유효한 식별자를 허용한다', () => {
    expect(isValidIdentifier('users')).toBe(true);
    expect(isValidIdentifier('_private')).toBe(true);
    expect(isValidIdentifier('schema.table_name')).toBe(true);
    expect(isValidIdentifier('Col_123')).toBe(true);
  });

  it('숫자로 시작하는 식별자를 거부한다', () => {
    expect(isValidIdentifier('123abc')).toBe(false);
  });

  it('특수 문자가 포함된 식별자를 거부한다', () => {
    expect(isValidIdentifier('table; DROP')).toBe(false);
    expect(isValidIdentifier('col-name')).toBe(false);
    expect(isValidIdentifier('name@domain')).toBe(false);
  });

  it('128자를 초과하는 식별자를 거부한다', () => {
    const long = 'a' + 'b'.repeat(128); // 129자
    expect(isValidIdentifier(long)).toBe(false);
  });

  it('빈 문자열을 거부한다', () => {
    expect(isValidIdentifier('')).toBe(false);
  });

  it('공백만 있는 식별자를 거부한다', () => {
    expect(isValidIdentifier('   ')).toBe(false);
  });
});
