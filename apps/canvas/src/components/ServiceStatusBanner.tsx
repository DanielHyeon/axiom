import { useServiceHealth } from '@/hooks/useServiceHealth';
import { AlertTriangle } from 'lucide-react';

export function ServiceStatusBanner() {
    const { down, allUp, refresh } = useServiceHealth();

    if (allUp || down.length === 0) return null;

    const names = down.map((s) => s.name).join(', ');

    return (
        <div
            className="glass-header relative z-10 flex items-center justify-between gap-3 px-5 py-2.5 text-sm"
            role="alert"
        >
            <div className="flex items-center gap-2 text-foreground">
                <AlertTriangle className="h-4 w-4 shrink-0 text-warning" />
                <span>
                    일부 서비스를 사용할 수 없습니다: <strong>{names}</strong>. 해당 기능이 동작하지 않을 수 있습니다.
                </span>
            </div>
            <button
                type="button"
                onClick={() => refresh()}
                className="shrink-0 rounded-lg border border-border/30 bg-muted/40 px-3 py-1 text-xs font-medium text-foreground transition-all duration-200 hover:bg-muted/60"
            >
                다시 확인
            </button>
        </div>
    );
}
