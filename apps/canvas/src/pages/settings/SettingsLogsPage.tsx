import React, { useState } from 'react';

type LogTab = 'explorer' | 'ai-analysis';

/** 설정 > 로그. 탭: Explorer(시스템/앱 로그), AI 분석 로그. 추후 로그 API 연동. */
export const SettingsLogsPage: React.FC = () => {
  const [tab, setTab] = useState<LogTab>('explorer');
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-foreground">로그</h2>
      <div className="flex gap-1 border-b border-border" role="tablist" aria-label="로그 탭">
        <button
          type="button"
          role="tab"
          aria-label="Explorer 로그"
          onClick={() => setTab('explorer')}
          className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === 'explorer' ? 'border-primary text-primary' : 'border-transparent text-secondary-foreground hover:text-foreground hover:border-border'}`}
        >
          Explorer
        </button>
        <button
          type="button"
          role="tab"
          aria-label="AI 분석 로그"
          onClick={() => setTab('ai-analysis')}
          className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === 'ai-analysis' ? 'border-primary text-primary' : 'border-transparent text-secondary-foreground hover:text-foreground hover:border-border'}`}
        >
          AI 분석
        </button>
      </div>
      {tab === 'explorer' && (
        <p className="text-sm text-secondary-foreground">시스템·앱 로그 조회 기능은 추후 연동됩니다.</p>
      )}
      {tab === 'ai-analysis' && (
        <p className="text-sm text-secondary-foreground">AI 분석 로그 조회 기능은 추후 연동됩니다.</p>
      )}
    </div>
  );
};
