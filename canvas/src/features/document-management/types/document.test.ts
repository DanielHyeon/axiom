/**
 * HITL FSM 상태 전이 가드 테스트.
 * 고위험 플로우: 잘못된 상태 전이가 허용되면 데이터 무결성 위험.
 */

import { describe, it, expect } from 'vitest';
import { canTransition, VALID_TRANSITIONS, ACTION_TO_STATUS } from './document';
import type { DocumentStatus, ReviewAction } from './document';

describe('canTransition — HITL FSM 가드', () => {
  it('draft → in_review 허용', () => {
    expect(canTransition('draft', 'in_review')).toBe(true);
  });

  it('in_review → approved 허용', () => {
    expect(canTransition('in_review', 'approved')).toBe(true);
  });

  it('in_review → rejected 허용', () => {
    expect(canTransition('in_review', 'rejected')).toBe(true);
  });

  it('in_review → changes_requested 허용', () => {
    expect(canTransition('in_review', 'changes_requested')).toBe(true);
  });

  it('draft → approved 차단 (검토 없이 직접 승인 불가)', () => {
    expect(canTransition('draft', 'approved')).toBe(false);
  });

  it('approved → draft 차단 (최종 상태)', () => {
    expect(canTransition('approved', 'draft')).toBe(false);
  });

  it('rejected → draft 허용 (재작성 가능)', () => {
    expect(canTransition('rejected', 'draft')).toBe(true);
  });

  it('changes_requested → in_review 허용 (수정 후 재검토)', () => {
    expect(canTransition('changes_requested', 'in_review')).toBe(true);
  });

  it('changes_requested → approved 차단 (재검토 없이 직접 승인 불가)', () => {
    expect(canTransition('changes_requested', 'approved')).toBe(false);
  });

  it('approved 상태에서는 어떤 전이도 불가', () => {
    const allStatuses: DocumentStatus[] = ['draft', 'in_review', 'approved', 'rejected', 'changes_requested'];
    for (const target of allStatuses) {
      expect(canTransition('approved', target)).toBe(false);
    }
  });
});

describe('ACTION_TO_STATUS — 액션→상태 매핑', () => {
  it('모든 ReviewAction이 매핑되어 있다', () => {
    const actions: ReviewAction[] = ['submit_for_review', 'approve', 'reject', 'request_changes', 'resubmit'];
    for (const action of actions) {
      expect(ACTION_TO_STATUS[action]).toBeDefined();
    }
  });

  it('approve → approved', () => {
    expect(ACTION_TO_STATUS.approve).toBe('approved');
  });

  it('submit_for_review → in_review', () => {
    expect(ACTION_TO_STATUS.submit_for_review).toBe('in_review');
  });
});

describe('VALID_TRANSITIONS — 전이 규칙 완전성', () => {
  it('모든 DocumentStatus가 전이 규칙에 정의되어 있다', () => {
    const allStatuses: DocumentStatus[] = ['draft', 'in_review', 'approved', 'rejected', 'changes_requested'];
    for (const status of allStatuses) {
      expect(VALID_TRANSITIONS[status]).toBeDefined();
      expect(Array.isArray(VALID_TRANSITIONS[status])).toBe(true);
    }
  });
});
