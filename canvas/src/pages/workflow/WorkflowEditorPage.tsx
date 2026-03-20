/**
 * WorkflowEditorPage — 워크플로 에디터 페이지
 *
 * GWT(Given-When-Then) 기반 정책 워크플로를 시각적으로 편집하는 페이지.
 * 전체 화면을 WorkflowEditorLayout에 위임한다.
 */

import { useTranslation } from 'react-i18next';
import { WorkflowEditorLayout } from '@/features/workflow-editor/components/WorkflowEditorLayout';

export const WorkflowEditorPage: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 페이지 헤더 */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border bg-card shrink-0">
        <div>
          <h1 className="text-lg font-bold text-foreground">
            {t('workflowEditor.title')}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {t('workflowEditor.subtitle')}
          </p>
        </div>
      </header>

      {/* 에디터 본문 */}
      <div className="flex-1 min-h-0">
        <WorkflowEditorLayout />
      </div>
    </div>
  );
};
