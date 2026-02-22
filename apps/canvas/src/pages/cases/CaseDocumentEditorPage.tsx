import React from 'react';
import { useDocumentParams } from '@/lib/routes/params';
import { DocumentEditorPage } from '../documents/DocumentEditorPage';

/** 케이스 컨텍스트 문서 편집. Phase 1에서 caseId/docId 연동 강화. */
export const CaseDocumentEditorPage: React.FC = () => {
  useDocumentParams(); // validate caseId, docId
  return <DocumentEditorPage />;
};
