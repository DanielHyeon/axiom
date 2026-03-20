/**
 * DomainModelerPage — /data/domain 라우트 페이지
 *
 * ObjectTypeModeler를 감싸는 페이지 래퍼.
 */

import React from 'react';
import { ObjectTypeModeler } from '@/features/domain/components/ObjectTypeModeler';

export const DomainModelerPage: React.FC = () => {
  return <ObjectTypeModeler />;
};
