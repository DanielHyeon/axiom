import { describe, it, expect, vi, beforeEach } from 'vitest';
import { exportToCsv } from './csvExport';

// ---------------------------------------------------------------------------
// DOM mock: Blob, URL, document.createElement 등은 jsdom 환경에서 제공됨.
// URL.createObjectURL / revokeObjectURL은 jsdom에 없으므로 mock 처리.
// ---------------------------------------------------------------------------

beforeEach(() => {
  // URL.createObjectURL / revokeObjectURL mock
  vi.stubGlobal('URL', {
    ...globalThis.URL,
    createObjectURL: vi.fn(() => 'blob:mock-url'),
    revokeObjectURL: vi.fn(),
  });
});

// ---------------------------------------------------------------------------
// 헬퍼: Blob 내용을 텍스트로 읽기
// ---------------------------------------------------------------------------

/** exportToCsv가 생성하는 Blob을 캡처하기 위한 spy */
function captureBlob(): { getBlob: () => Blob | null } {
  let captured: Blob | null = null;
  const origBlob = globalThis.Blob;

  // Blob 생성자를 감시하여 마지막으로 생성된 Blob을 캡처
  vi.spyOn(globalThis, 'Blob').mockImplementation((...args) => {
    const blob = new origBlob(...(args as [BlobPart[]?, BlobPropertyBag?]));
    captured = blob;
    return blob;
  });

  return { getBlob: () => captured };
}

async function blobToText(blob: Blob): Promise<string> {
  return blob.text();
}

// ---------------------------------------------------------------------------
// exportToCsv
// ---------------------------------------------------------------------------

describe('exportToCsv', () => {
  it('기본 CSV 생성: 헤더 + 데이터 행', async () => {
    const spy = captureBlob();

    exportToCsv(
      [{ name: 'Name' }, { name: 'Age' }],
      [['Alice', 30], ['Bob', 25]],
    );

    const blob = spy.getBlob();
    expect(blob).not.toBeNull();

    const text = await blobToText(blob!);
    // BOM 문자 제거 후 확인
    const csv = text.replace(/^\uFEFF/, '');
    const lines = csv.split('\n');

    expect(lines[0]).toBe('Name,Age');
    expect(lines[1]).toBe('Alice,30');
    expect(lines[2]).toBe('Bob,25');
  });

  it('특수문자 이스케이프: 쉼표 포함 값은 따옴표로 감싸기', async () => {
    const spy = captureBlob();

    exportToCsv(
      [{ name: 'Value' }],
      [['hello, world']],
    );

    const text = await blobToText(spy.getBlob()!);
    const csv = text.replace(/^\uFEFF/, '');
    expect(csv).toContain('"hello, world"');
  });

  it('특수문자 이스케이프: 따옴표는 두 번 반복 ("")', async () => {
    const spy = captureBlob();

    exportToCsv(
      [{ name: 'Quote' }],
      [['say "hello"']],
    );

    const text = await blobToText(spy.getBlob()!);
    const csv = text.replace(/^\uFEFF/, '');
    expect(csv).toContain('"say ""hello"""');
  });

  it('특수문자 이스케이프: 줄바꿈 포함 값은 따옴표로 감싸기', async () => {
    const spy = captureBlob();

    exportToCsv(
      [{ name: 'Text' }],
      [['line1\nline2']],
    );

    const text = await blobToText(spy.getBlob()!);
    const csv = text.replace(/^\uFEFF/, '');
    expect(csv).toContain('"line1\nline2"');
  });

  it('한국어 문자열 처리', async () => {
    const spy = captureBlob();

    exportToCsv(
      [{ name: '이름' }, { name: '직급' }],
      [['김철수', '부장'], ['이영희', '과장']],
    );

    const text = await blobToText(spy.getBlob()!);
    const csv = text.replace(/^\uFEFF/, '');
    const lines = csv.split('\n');

    expect(lines[0]).toBe('이름,직급');
    expect(lines[1]).toBe('김철수,부장');
  });

  it('null/undefined 셀 → 빈 문자열로 처리', async () => {
    const spy = captureBlob();

    exportToCsv(
      [{ name: 'A' }, { name: 'B' }],
      [[null, undefined]],
    );

    const text = await blobToText(spy.getBlob()!);
    const csv = text.replace(/^\uFEFF/, '');
    const lines = csv.split('\n');
    expect(lines[1]).toBe(',');
  });

  it('빈 데이터 → 헤더만 출력', async () => {
    const spy = captureBlob();

    exportToCsv([{ name: 'Col1' }], []);

    const text = await blobToText(spy.getBlob()!);
    const csv = text.replace(/^\uFEFF/, '');
    expect(csv).toBe('Col1\n');
  });

  it('BOM (Byte Order Mark) 포함: UTF-8 BOM 접두사 존재', async () => {
    const spy = captureBlob();

    exportToCsv([{ name: 'A' }], [['1']]);

    const text = await blobToText(spy.getBlob()!);
    expect(text.charCodeAt(0)).toBe(0xfeff);
  });

  it('다운로드 링크 생성: a.click() 호출됨', () => {
    const clickSpy = vi.fn();
    vi.spyOn(document, 'createElement').mockReturnValue({
      set href(_: string) { /* noop */ },
      set download(_: string) { /* noop */ },
      click: clickSpy,
    } as unknown as HTMLAnchorElement);

    exportToCsv([{ name: 'A' }], [['1']]);
    expect(clickSpy).toHaveBeenCalledOnce();
  });

  it('헤더 컬럼명에 쉼표 → 따옴표 이스케이프', async () => {
    const spy = captureBlob();

    exportToCsv([{ name: 'A, B' }], [['value']]);

    const text = await blobToText(spy.getBlob()!);
    const csv = text.replace(/^\uFEFF/, '');
    expect(csv.startsWith('"A, B"')).toBe(true);
  });
});
