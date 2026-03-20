import { useState, useEffect } from 'react';
import type { Alert } from '../types/watch';

// This hook is designed specifically for the Header Notification Bell
// to listen to the global event dispatched by `useAlerts` without requiring
// the entire Dashboard component tree to re-render.
export function useNotificationBell() {
    const [unreadCount, setUnreadCount] = useState(1); // from INITIAL_ALERTS above
    const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);

    useEffect(() => {
        const handleNewAlert = (event: Event) => {
            const customEvent = event as CustomEvent<Alert>;
            const newAlert = customEvent.detail;

            setUnreadCount(prev => prev + 1);
            setRecentAlerts(prev => [newAlert, ...prev].slice(0, 5)); // Keep last 5
        };

        window.addEventListener('axiom:new_alert', handleNewAlert);
        return () => window.removeEventListener('axiom:new_alert', handleNewAlert);
    }, []);

    const clearBadge = () => {
        setUnreadCount(0);
    };

    return {
        unreadCount,
        recentAlerts,
        clearBadge
    };
}
