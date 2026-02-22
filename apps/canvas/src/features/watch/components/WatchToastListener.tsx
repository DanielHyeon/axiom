import { useEffect } from 'react';
import { toast } from 'sonner';
import type { Alert } from '../types/watch';

/**
 * axiom:new_alert 이벤트 수신 시 심각도별 토스트.
 * CRITICAL/high → toast.error (수동 닫힘), warning → toast.warning, MEDIUM 이하 → 짧은 duration.
 */
export function WatchToastListener() {
    useEffect(() => {
        const handleNewAlert = (event: Event) => {
            const customEvent = event as CustomEvent<Alert>;
            const alert = customEvent.detail;
            const title = alert.title;
            const description = alert.description ?? '';

            if (alert.severity === 'critical') {
                toast.error(title, {
                    description,
                    duration: Number.POSITIVE_INFINITY,
                    dismissible: true
                });
            } else if (alert.severity === 'warning') {
                toast.warning(title, {
                    description,
                    duration: 15_000,
                    dismissible: true
                });
            } else {
                toast(title, {
                    description,
                    duration: 5000,
                    dismissible: true
                });
            }
        };

        window.addEventListener('axiom:new_alert', handleNewAlert);
        return () => window.removeEventListener('axiom:new_alert', handleNewAlert);
    }, []);

    return null;
}
