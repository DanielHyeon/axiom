import { AlertStats } from './components/AlertStats';
import { PriorityFilter } from './components/PriorityFilter';
import { AlertFeed } from './components/AlertFeed';
import { AlertRuleEditor } from './components/AlertRuleEditor';
import { EventTimeline } from './components/EventTimeline';
import { useAlerts } from '@/features/watch/hooks/useAlerts';
import { useWatchStore } from '@/features/watch/store/useWatchStore';
import { useMemo, useState } from 'react';
import { BellRing, List, LayoutGrid, Settings2 } from 'lucide-react';

export function WatchDashboardPage() {
    const { getFilteredAlerts, markAsRead } = useAlerts();
    const { filters } = useWatchStore();
    const [view, setView] = useState<'feed' | 'timeline' | 'rules'>('feed');

    const filteredAlerts = useMemo(
        () => getFilteredAlerts(filters.query, filters.severity),
        [getFilteredAlerts, filters]
    );

    return (
        <div className="flex flex-col h-full bg-background text-foreground max-w-7xl mx-auto p-8 overflow-hidden">
            <div className="flex items-center justify-between mb-8 shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                        <BellRing className="text-primary" size={20} aria-hidden />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-foreground">통합 관제 및 알람</h1>
                        <p className="text-sm text-secondary-foreground">네트워크 지연 및 시스템 이상 징후 실시간 모니터링</p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <PriorityFilter />
                    <div className="flex rounded-lg border border-border bg-card overflow-hidden" role="tablist" aria-label="보기 전환">
                        <button
                            type="button"
                            role="tab"
                            aria-label="알림 피드"
                            onClick={() => setView('feed')}
                            className={`flex items-center gap-2 px-3 py-2 text-sm ${view === 'feed' ? 'bg-primary/15 text-primary font-medium' : 'text-secondary-foreground hover:bg-secondary'}`}
                        >
                            <List size={18} aria-hidden />
                            <span>피드</span>
                        </button>
                        <button
                            type="button"
                            role="tab"
                            aria-label="이벤트 타임라인"
                            onClick={() => setView('timeline')}
                            className={`flex items-center gap-2 px-3 py-2 text-sm ${view === 'timeline' ? 'bg-primary/15 text-primary font-medium' : 'text-secondary-foreground hover:bg-secondary'}`}
                        >
                            <LayoutGrid size={18} aria-hidden />
                            <span>타임라인</span>
                        </button>
                        <button
                            type="button"
                            role="tab"
                            aria-label="알림 규칙 설정"
                            onClick={() => setView('rules')}
                            className={`flex items-center gap-2 px-3 py-2 text-sm ${view === 'rules' ? 'bg-primary/15 text-primary font-medium' : 'text-secondary-foreground hover:bg-secondary'}`}
                        >
                            <Settings2 size={18} aria-hidden />
                            <span>알림 규칙</span>
                        </button>
                    </div>
                </div>
            </div>

            <div className="shrink-0">
                <AlertStats />
            </div>

            <div className="flex-1 min-h-0 flex flex-col pt-4">
                {view === 'feed' && <AlertFeed />}
                {view === 'timeline' && (
                    <div className="flex flex-col h-full bg-card border border-border rounded-lg overflow-auto p-4">
                        <EventTimeline events={filteredAlerts} onMarkAsRead={markAsRead} />
                    </div>
                )}
                {view === 'rules' && (
                    <div className="flex flex-col h-full bg-card border border-border rounded-lg overflow-auto p-4">
                        <AlertRuleEditor />
                    </div>
                )}
            </div>
        </div>
    );
}
