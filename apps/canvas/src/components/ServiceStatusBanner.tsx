import { useServiceHealth } from '@/hooks/useServiceHealth';

/**
 * Core/Vision/Oracle 중 하나라도 down이면 상단 배너 표시.
 */
export function ServiceStatusBanner() {
    const { down, allUp, refresh } = useServiceHealth();

    if (allUp || down.length === 0) return null;

    const names = down.map((s) => s.name).join(', ');

    return (
        <div
            className="flex items-center justify-between px-4 py-2 bg-amber-950 border-b border-amber-800 text-amber-200 text-sm"
            role="alert"
        >
            <span>
                일부 서비스를 사용할 수 없습니다: <strong>{names}</strong>. 해당 기능이 동작하지 않을 수 있습니다.
            </span>
            <button
                type="button"
                onClick={() => refresh()}
                className="px-2 py-1 rounded border border-amber-700 hover:bg-amber-900/50 text-amber-100 text-xs"
            >
                다시 확인
            </button>
        </div>
    );
}
