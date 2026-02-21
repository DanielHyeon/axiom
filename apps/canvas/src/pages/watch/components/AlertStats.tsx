export function AlertStats() {
    return (
        <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-[#1a1a1a] border border-neutral-800 rounded-lg p-5">
                <div className="text-neutral-400 text-sm font-medium mb-1">총 알림 건수</div>
                <div className="text-2xl font-bold text-neutral-100">1,204</div>
                <div className="text-xs text-neutral-500 mt-2">+12% from yesterday</div>
            </div>
            <div className="bg-[#1a1a1a] border border-red-900/50 rounded-lg p-5">
                <div className="text-red-400 text-sm font-medium mb-1">처리 지연 (Critical)</div>
                <div className="text-2xl font-bold text-red-500">28</div>
                <div className="text-xs text-red-500/70 mt-2">즉시 조치 필요</div>
            </div>
            <div className="bg-[#1a1a1a] border border-amber-900/50 rounded-lg p-5">
                <div className="text-amber-400 text-sm font-medium mb-1">경고 (Warning)</div>
                <div className="text-2xl font-bold text-amber-500">142</div>
                <div className="text-xs text-amber-500/70 mt-2">모니터링 요망</div>
            </div>
            <div className="bg-[#1a1a1a] border border-blue-900/50 rounded-lg p-5">
                <div className="text-blue-400 text-sm font-medium mb-1">정보 (Info)</div>
                <div className="text-2xl font-bold text-blue-500">1,034</div>
                <div className="text-xs text-blue-500/70 mt-2">정상 운영중</div>
            </div>
        </div>
    );
}
