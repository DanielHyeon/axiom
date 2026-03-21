/**
 * MondrianXmlEditor 컴포넌트 테스트.
 *
 * XML 편집기의 렌더링, 모드 전환, 버튼 동작, 상태 바를 검증한다.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MondrianXmlEditor } from './MondrianXmlEditor';

// ─── 테스트 헬퍼 ──────────────────────────────────────────────

const SAMPLE_XML = '<Schema name="test"></Schema>';

function makeProps(overrides = {}) {
  return {
    value: SAMPLE_XML,
    onChange: vi.fn(),
    ...overrides,
  };
}

/** textarea 요소를 반환한다 */
function getTextarea(): HTMLTextAreaElement {
  return screen.getByPlaceholderText(
    'Mondrian XML을 입력하거나 파일을 업로드하세요...',
  ) as HTMLTextAreaElement;
}

// ─── 테스트 ───────────────────────────────────────────────────

describe('MondrianXmlEditor', () => {
  // ── 기본 렌더링 ──────────────────────────────────────────

  it('편집 모드가 기본이며 textarea가 표시된다', () => {
    render(<MondrianXmlEditor {...makeProps()} />);
    expect(getTextarea()).toBeDefined();
  });

  it('textarea에 value 값이 표시된다', () => {
    render(<MondrianXmlEditor {...makeProps()} />);
    expect(getTextarea().value).toBe(SAMPLE_XML);
  });

  // ── 모드 전환 ────────────────────────────────────────────

  it('미리보기 버튼 클릭 시 pre 태그로 전환된다', () => {
    render(<MondrianXmlEditor {...makeProps()} />);
    fireEvent.click(screen.getByText('미리보기'));
    // textarea 사라지고 pre에 XML 표시
    expect(
      screen.queryByPlaceholderText(
        'Mondrian XML을 입력하거나 파일을 업로드하세요...',
      ),
    ).toBeNull();
    expect(screen.getByText(SAMPLE_XML)).toBeDefined();
  });

  it('미리보기에서 편집 버튼 클릭 시 textarea로 복귀한다', () => {
    render(<MondrianXmlEditor {...makeProps()} />);
    fireEvent.click(screen.getByText('미리보기'));
    fireEvent.click(screen.getByText('편집'));
    expect(getTextarea()).toBeDefined();
  });

  it('빈 값일 때 미리보기 모드에서 안내 메시지를 표시한다', () => {
    render(<MondrianXmlEditor {...makeProps({ value: '' })} />);
    fireEvent.click(screen.getByText('미리보기'));
    expect(screen.getByText('내용이 없습니다')).toBeDefined();
  });

  // ── onChange 동작 ────────────────────────────────────────

  it('textarea 변경 시 onChange가 호출된다', () => {
    const onChange = vi.fn();
    render(<MondrianXmlEditor {...makeProps({ onChange })} />);
    fireEvent.change(getTextarea(), { target: { value: '<Schema/>' } });
    expect(onChange).toHaveBeenCalledWith('<Schema/>');
  });

  // ── readOnly 동작 ────────────────────────────────────────

  it('readOnly 프로퍼티가 textarea에 전달된다', () => {
    render(<MondrianXmlEditor {...makeProps({ readOnly: true })} />);
    expect(getTextarea().readOnly).toBe(true);
  });

  // ── 상태 바 ──────────────────────────────────────────────

  it('상태 바에 문자 수가 표시된다', () => {
    render(<MondrianXmlEditor {...makeProps()} />);
    // SAMPLE_XML.length = 29
    expect(screen.getByText('29 문자')).toBeDefined();
  });

  it('상태 바에 줄 수가 표시된다', () => {
    render(<MondrianXmlEditor {...makeProps()} />);
    expect(screen.getByText('1 줄')).toBeDefined();
  });

  it('여러 줄 XML의 줄 수가 정확히 표시된다', () => {
    const multiLineXml = '<Schema>\n  <Cube/>\n</Schema>';
    render(<MondrianXmlEditor {...makeProps({ value: multiLineXml })} />);
    expect(screen.getByText('3 줄')).toBeDefined();
  });

  // ── 검증 버튼 ────────────────────────────────────────────

  it('onValidate 제공 시 검증 버튼이 표시되고 클릭 시 콜백이 호출된다', () => {
    const onValidate = vi.fn();
    render(<MondrianXmlEditor {...makeProps({ onValidate })} />);
    const validateBtn = screen.getByText('검증');
    fireEvent.click(validateBtn);
    expect(onValidate).toHaveBeenCalledWith(SAMPLE_XML);
  });

  it('onValidate 미제공 시 검증 버튼이 표시되지 않는다', () => {
    render(<MondrianXmlEditor {...makeProps()} />);
    expect(screen.queryByText('검증')).toBeNull();
  });
});
