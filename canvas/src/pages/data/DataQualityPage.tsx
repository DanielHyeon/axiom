/**
 * DataQualityPage — 데이터 품질 대시보드 페이지
 * DQ 점수 카드, 규칙 테이블, 인시던트 타임라인, 추이 차트를 통합
 * KAIR의 DataQuality.vue + IncidentManager.vue를 Axiom 패턴으로 이식
 */
import { useTranslation } from 'react-i18next';
import { ShieldCheck, Plus } from 'lucide-react';
import { DQScoreCard } from '@/features/data-quality/components/DQScoreCard';
import { DQRuleTable } from '@/features/data-quality/components/DQRuleTable';
import { DQTestRunner } from '@/features/data-quality/components/DQTestRunner';
import { IncidentTimeline } from '@/features/data-quality/components/IncidentTimeline';
import { IncidentDetail } from '@/features/data-quality/components/IncidentDetail';
import { DQTrendChart } from '@/features/data-quality/components/DQTrendChart';
import { useDQStore } from '@/features/data-quality/store/useDQStore';
import type { DQSubTab } from '@/features/data-quality/store/useDQStore';

// 서브탭 정의
const TABS: { key: DQSubTab; label: string }[] = [
  { key: 'test-cases', label: '테스트 케이스' },
  { key: 'incidents', label: '인시던트' },
  { key: 'trend', label: '추이' },
];

export function DataQualityPage() {
  const { t } = useTranslation();
  const { activeTab, setActiveTab, setShowCreateDialog } = useDQStore();

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 flex flex-col overflow-y-auto px-8 py-6 gap-6 max-w-7xl mx-auto w-full">
        {/* 헤더 */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <ShieldCheck className="text-primary" size={20} aria-hidden />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">
                {t('dataQuality.title', '데이터 품질')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('dataQuality.subtitle', '품질 테스트로 데이터에 대한 신뢰를 구축하세요.')}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowCreateDialog(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:bg-primary/90 transition-colors"
          >
            <Plus size={16} />
            테스트 케이스 추가
          </button>
        </div>

        {/* 서브탭 */}
        <div className="flex gap-1 border-b border-border">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors -mb-px ${
                activeTab === tab.key
                  ? 'text-primary border-b-2 border-primary'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* 통계 카드 (공통) */}
        <DQScoreCard />

        {/* 탭 컨텐츠 */}
        {activeTab === 'test-cases' && <DQRuleTable />}
        {activeTab === 'incidents' && <IncidentTimeline />}
        {activeTab === 'trend' && <DQTrendChart />}
      </div>

      {/* 오버레이: 테스트 케이스 생성 다이얼로그 */}
      <DQTestRunner />

      {/* 오버레이: 규칙 상세 패널 */}
      <IncidentDetail />
    </div>
  );
}
