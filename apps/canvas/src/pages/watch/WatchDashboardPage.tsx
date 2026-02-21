import { AlertStats } from './components/AlertStats';
import { PriorityFilter } from './components/PriorityFilter';
import { AlertFeed } from './components/AlertFeed';
import { BellRing } from 'lucide-react';

export function WatchDashboardPage() {
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

                <PriorityFilter />
            </div>

            <div className="shrink-0">
                <AlertStats />
            </div>

            <div className="flex-1 min-h-0 flex flex-col pt-4">
                <AlertFeed />
            </div>
        </div>
    );
}
