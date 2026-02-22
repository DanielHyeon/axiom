import React from 'react';
import { useCaseParams } from '@/lib/routes/params';
import { DocumentListPage } from '../documents/DocumentListPage';

/** 케이스 컨텍스트 문서 목록. Phase 1에서 caseId 연동 강화. */
export const CaseDocumentsListPage: React.FC = () => {
  useCaseParams(); // validate caseId
  return <DocumentListPage />;
};
