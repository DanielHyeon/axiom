/**
 * 입력 검증/정제 유틸 -- 3단계 방어 전략.
 *
 * 1단계: 기본 텍스트 필드 -- 길이 제한 + 위험 문자 제거
 * 2단계: HTML/Markdown 렌더링 -- allowlist 기반 태그 허용
 * 3단계: URL/파일명/식별자 -- 스키마/문자셋 검증
 */

// ── 1단계: 기본 텍스트 정제 ──

/**
 * 기본 텍스트 정제 -- 길이 제한 + HTML 엔티티 이스케이프.
 *
 * XSS 방어를 위해 <, >, &, ", ' 문자를 HTML 엔티티로 치환한다.
 * maxLength를 초과하는 부분은 잘라낸다.
 */
export function sanitizeText(input: string, maxLength = 1000): string {
  // 빈 문자열 빠른 반환
  if (!input) return '';

  const trimmed = input.slice(0, maxLength);
  return trimmed
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

// ── 2단계: HTML 태그 제거 ──

/**
 * HTML 태그 제거 -- allowlist 기반 (React JSX 외부 렌더링용).
 *
 * allowedTags가 비어 있으면 모든 태그를 제거한다.
 * allowedTags에 포함된 태그만 유지하고 나머지는 제거한다.
 */
export function stripHtmlTags(input: string, allowedTags: string[] = []): string {
  if (!input) return '';

  // 허용 태그 없음 → 모든 태그 제거
  if (allowedTags.length === 0) {
    return input.replace(/<[^>]*>/g, '');
  }

  // 허용된 태그 패턴 생성 (대소문자 무시)
  const allowed = new Set(allowedTags.map((t) => t.toLowerCase()));

  // 모든 태그를 찾아서 허용 목록에 없으면 제거
  return input.replace(/<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/gi, (match, tagName: string) => {
    return allowed.has(tagName.toLowerCase()) ? match : '';
  });
}

// ── 3단계: URL / 파일명 / 식별자 검증 ──

/**
 * URL 검증 -- http/https 스키마만 허용.
 *
 * javascript:, data:, ftp: 등 위험한 프로토콜을 차단한다.
 * 유효하지 않은 URL이면 빈 문자열을 반환한다.
 */
export function sanitizeUrl(input: string): string {
  if (!input) return '';

  try {
    const url = new URL(input);
    if (!['http:', 'https:'].includes(url.protocol)) {
      return '';
    }
    return url.toString();
  } catch {
    return '';
  }
}

/**
 * 파일명 정제 -- 경로 순회(path traversal) 방지.
 *
 * 슬래시, 백슬래시, 콜론 등 파일 시스템 위험 문자를 밑줄로 치환한다.
 * ".." 시퀀스를 밑줄로 치환하여 디렉터리 이탈을 방지한다.
 */
export function sanitizeFilename(input: string, maxLength = 255): string {
  if (!input) return '';

  return input
    .replace(/[/\\:*?"<>|]/g, '_')   // 파일시스템 금지 문자 치환
    .replace(/\.\./g, '_')           // 경로 순회 ".." 방지
    .replace(/^\s+|\s+$/g, '')       // 양쪽 공백 제거
    .slice(0, maxLength);
}

/**
 * SQL 식별자 검증 -- 알파벳, 숫자, 밑줄, 점만 허용.
 *
 * 시작 문자는 알파벳 또는 밑줄이어야 한다.
 * 최대 128자까지 허용한다.
 */
export function isValidIdentifier(input: string): boolean {
  if (!input) return false;
  return /^[A-Za-z_][A-Za-z0-9_.]{0,127}$/.test(input);
}
