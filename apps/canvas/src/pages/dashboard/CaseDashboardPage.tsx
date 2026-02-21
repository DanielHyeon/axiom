import { useCases } from '@/features/case-dashboard/hooks/useCases';

export function CaseDashboardPage() {
    const { data: cases, isLoading, error } = useCases();

    return (
        <div className="p-6">
            <h1 className="text-3xl font-bold tracking-tight mb-8">대시보드</h1>

            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6">
                <h2 className="text-xl font-semibold mb-4 text-white">내 할당 업무 (My Workitems)</h2>

                {isLoading && (
                    <div className="space-y-3 animate-pulse">
                        <div className="h-12 bg-neutral-800 rounded w-full"></div>
                        <div className="h-12 bg-neutral-800 rounded w-full"></div>
                        <div className="h-12 bg-neutral-800 rounded w-full"></div>
                    </div>
                )}

                {error && (
                    <div className="p-4 bg-red-900/50 border border-red-500 rounded text-red-200">
                        데이터를 불러오는 중 오류가 발생했습니다.
                    </div>
                )}

                {cases && (
                    <div className="grid gap-4">
                        {cases.map((c) => (
                            <div
                                key={c.id}
                                className="p-4 rounded-lg border border-neutral-800 bg-neutral-950 hover:bg-neutral-800/50 cursor-pointer transition-colors flex items-center justify-between"
                            >
                                <div>
                                    <h3 className="font-medium text-lg text-white mb-1">{c.title}</h3>
                                    <p className="text-sm text-neutral-400">ID: {c.id} • 생성일: {new Date(c.createdAt).toLocaleDateString()}</p>
                                </div>
                                <div className="flex items-center gap-3">
                                    <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${c.priority === 'HIGH' || c.priority === 'CRITICAL' ? 'bg-red-500/20 text-red-500' : 'bg-blue-500/20 text-blue-500'
                                        }`}>
                                        {c.priority}
                                    </span>
                                    <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${c.status === 'COMPLETED' ? 'bg-green-500/20 text-green-500' :
                                            c.status === 'IN_PROGRESS' ? 'bg-yellow-500/20 text-yellow-500' :
                                                'bg-neutral-500/20 text-neutral-400'
                                        }`}>
                                        {c.status.replace('_', ' ')}
                                    </span>
                                </div>
                            </div>
                        ))}
                        {cases.length === 0 && <p className="text-neutral-500 text-sm">할당된 케이스가 없습니다.</p>}
                    </div>
                )}
            </div>
        </div>
    );
}
