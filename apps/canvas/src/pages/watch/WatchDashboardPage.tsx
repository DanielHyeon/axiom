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
        <div className="flex flex-col h-full bg-[#111111] max-w-7xl mx-auto p-8 overflow-hidden">
            <div className="flex items-center justify-between mb-8 shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                        <BellRing className="text-blue-500" size={20} />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-neutral-100">통합 관제 및 알람</h1>
                        <p className="text-sm text-neutral-400">네트워크 지연 및 시스템 이상 징후 실시간 모니터링</p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <PriorityFilter />
                    <div className="flex rounded-lg border border-neutral-800 overflow-hidden">
                        <button
                            type="button"
                            onClick={() => setView('feed')}
                            className={`p-2 ${view === 'feed' ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-500 hover:bg-neutral-800/50'}`}
                            title="피드"
                        >
                            <List size={18} />
                        </button>
                        <button
                            type="button"
                            onClick={() => setView('timeline')}
                            className={`p-2 ${view === 'timeline' ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-500 hover:bg-neutral-800/50'}`}
                            title="타임라인"
                        >
                            <LayoutGrid size={18} />
                        </button>
                        <button
                            type="button"
                            onClick={() => setView('rules')}
                            className={`p-2 ${view === 'rules' ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-500 hover:bg-neutral-800/50'}`}
                            title="알림 규칙"
                        >
                            <Settings2 size={18} />
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
                    <div className="flex flex-col h-full bg-[#161616] border border-neutral-800 rounded-lg overflow-auto p-4">
                        <EventTimeline events={filteredAlerts} onMarkAsRead={markAsRead} />
                    </div>
                )}
                {view === 'rules' && (
                    <div className="flex flex-col h-full bg-[#161616] border border-neutral-800 rounded-lg overflow-auto p-4">
                        <AlertRuleEditor />
                    </div>
                )}
            </div>
        </div>
    );
}
