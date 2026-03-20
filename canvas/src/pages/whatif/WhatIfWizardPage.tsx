/**
 * WhatIfWizardPage — 5단계 What-if 위자드 페이지
 *
 * WhatIfWizard 컴포넌트를 전체 화면으로 렌더링하는 페이지 래퍼.
 * /analysis/whatif/wizard 라우트에서 사용된다.
 */
import { WhatIfWizard } from '@/features/whatif/components/WhatIfWizard';

export function WhatIfWizardPage() {
  return (
    <div className="h-[calc(100vh-4rem)]">
      <WhatIfWizard />
    </div>
  );
}
