import { useState, useEffect, useCallback } from 'react';
import { checkServiceHealth, type ServiceStatus } from '@/lib/api/health';

const POLL_INTERVAL_MS = 60_000;

export function useServiceHealth() {
    const [statuses, setStatuses] = useState<ServiceStatus[]>([]);
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        setLoading(true);
        try {
            const result = await checkServiceHealth();
            setStatuses(result);
        } catch {
            setStatuses([
                { name: 'Core', status: 'down', error: 'Check failed' },
                { name: 'Vision', status: 'down', error: 'Check failed' },
                { name: 'Oracle', status: 'down', error: 'Check failed' }
            ]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh();
        const interval = setInterval(refresh, POLL_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [refresh]);

    const down = statuses.filter((s) => s.status === 'down');
    const allUp = down.length === 0;

    return { statuses, loading, down, allUp, refresh };
}
