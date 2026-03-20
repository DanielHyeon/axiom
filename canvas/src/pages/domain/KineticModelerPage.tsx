/**
 * KineticModelerPage — /data/domain/kinetic 라우트 페이지
 *
 * 도메인 모델러의 Kinetic(행동 모델) 편집기.
 * ActionType / Policy 의 GWT 규칙을 관리하는 3패널 레이아웃을 감싼다.
 */

import React from 'react';
import { DomainModelerLayout } from '@/features/domain-modeler/components/DomainModelerLayout';

export const KineticModelerPage: React.FC = () => {
  return <DomainModelerLayout />;
};
