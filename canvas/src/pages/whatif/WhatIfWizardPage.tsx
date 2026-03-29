/**
 * WhatIfWizardPage — What-if 위자드 페이지 래퍼
 *
 * /analysis/whatif/wizard 라우트에서 사용.
 * URL의 caseId를 스토어에 전달하고, WhatIfWizard를 전체 화면으로 렌더링.
 */
import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { WhatIfWizard } from '@/features/whatif-wizard/components/WhatIfWizard';
import { useWhatIfWizardStore } from '@/features/whatif-wizard/store/useWhatIfWizardStore';

export function WhatIfWizardPage() {
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('caseId') ?? 'demo_manufacturing';

  const setCaseId = useWhatIfWizardStore((s) => s.setCaseId);

  useEffect(() => {
    setCaseId(caseId);
  }, [caseId, setCaseId]);

  return (
    <div className="h-[calc(100vh-4rem)]">
      <WhatIfWizard />
    </div>
  );
}
