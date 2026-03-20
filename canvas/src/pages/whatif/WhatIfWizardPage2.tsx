/**
 * WhatIfWizardPage2 — What-if 위자드 v2 페이지
 *
 * DAG + Event Fork 통합 위자드를 전체 화면으로 렌더링한다.
 * URL에서 case_id를 추출하여 위자드에 전달한다.
 *
 * 라우트: /analysis/whatif/wizard2 또는 /analysis/whatif/wizard?v=2
 */
import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { WhatIfWizard } from '@/features/whatif-wizard/components/WhatIfWizard';
import { useWhatIfWizardStore } from '@/features/whatif-wizard/store/useWhatIfWizardStore';

export function WhatIfWizardPage2() {
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('caseId') ?? 'demo_manufacturing';

  // URL의 caseId를 스토어에 설정
  const setCaseId = useWhatIfWizardStore((s) => s.setCaseId);
  const setScenarioName = useWhatIfWizardStore((s) => s.setScenarioName);
  const scenarioName = useWhatIfWizardStore((s) => s.scenarioName);

  useEffect(() => {
    // caseId를 스토어에 주입하여 모든 Step에서 사용 가능하게 함
    setCaseId(caseId);
    // 시나리오 이름이 비어있으면 초기화
    if (!scenarioName) {
      setScenarioName('');
    }
  }, [caseId, scenarioName, setCaseId, setScenarioName]);

  return (
    <div className="h-[calc(100vh-4rem)]">
      <WhatIfWizard />
    </div>
  );
}
