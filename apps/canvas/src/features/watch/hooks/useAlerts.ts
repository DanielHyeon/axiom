import { useState, useEffect, useCallback } from 'react';
import type { Alert, AlertSeverity } from '../types/watch';
import { fetchAlerts, markAlertAsRead, markAllAlertsAsRead } from '@/lib/api/watch';
import { useAuthStore } from '@/stores/authStore';

const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true';

// Mock initial data
const INITIAL_ALERTS: Alert[] = [
    {
        id: 'a1',
        title: '물류센터 A 체류시간 초과',
        description: '입고 피킹 구역에서 평균 체류시간이 30%를 초과했습니다.',
        severity: 'critical',
        timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
        isRead: false,
        sourceNodeId: 'r_centerA',
        metadata: { diff: '+32.4%', threshold: '45min' }
    },
    {
        id: 'a2',
        title: 'ERP 시스템 지연 감지',
        description: 'API 응답 속도가 허용치를 초과하여 저하되고 있습니다.',
        severity: 'warning',
        timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
        isRead: true,
        sourceNodeId: 'r_erp'
    },
    {
        id: 'a3',
        title: '배송목표 달성 순항중',
        description: '전일 대비 배송 완료율이 3% 상승했습니다.',
        severity: 'info',
        timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
        isRead: true,
        sourceNodeId: 'kpi_logistics'
    }
];

export function useAlerts() {
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Initial load
    useEffect(() => {
        if (USE_MOCK) {
            const timer = setTimeout(() => {
                setAlerts(INITIAL_ALERTS);
                setIsLoading(false);
            }, 800);
            return () => clearTimeout(timer);
        } else {
            fetchAlerts().then(data => {
                // Backend return format mapped to frontend format if necessary
                // Assumes data wrapper is stripped in createApiClient interceptor
                const fetched = (data as any).data || data;
                setAlerts(fetched);
            }).catch(e => {
                console.error("Failed to load alerts:", e);
                // Graceful fallback to empty array on fail
                setAlerts([]);
            }).finally(() => {
                setIsLoading(false);
            });
        }
    }, []);

    // WebSocket / SSE Simulation
    useEffect(() => {
        if (isLoading) return;

        if (USE_MOCK) {
            const interval = setInterval(() => {
                // Simulate random new alerts every 15-30 seconds
                if (Math.random() > 0.6) {
                    const severities: AlertSeverity[] = ['critical', 'warning', 'info'];
                    const randomSeverity = severities[Math.floor(Math.random() * severities.length)];

                    const newAlert: Alert = {
                        id: `a${Date.now()}`,
                        title: `실시간 감지 알람 (${Math.floor(Math.random() * 100)})`,
                        description: '시스템에서 새로운 패턴 또는 지연 징후가 포착되었습니다.',
                        severity: randomSeverity,
                        timestamp: new Date().toISOString(),
                        isRead: false,
                    };

                    setAlerts(prev => [newAlert, ...prev]);

                    // Trigger global event for components outside this React tree to listen (like the Bell in Header)
                    window.dispatchEvent(new CustomEvent('axiom:new_alert', { detail: newAlert }));
                }
            }, 15000);

            return () => clearInterval(interval);
        } else {
            const token = useAuthStore.getState().accessToken;
            if (!token) return;

            const baseUrl = import.meta.env.VITE_CORE_URL;
            const eventSource = new EventSource(`${baseUrl}/api/v1/watches/stream?token=${token}`);

            eventSource.addEventListener('alert', (event) => {
                try {
                    const data = JSON.parse(event.data);

                    const newAlert: Alert = {
                        id: data.alert_id,
                        title: data.message,
                        description: data.details || `이벤트 발생: ${data.event_type}`,
                        severity: (data.severity || 'info').toLowerCase(),
                        timestamp: data.triggered_at || new Date().toISOString(),
                        isRead: data.status === 'acknowledged',
                        metadata: data.metadata,
                        sourceNodeId: data.case_id
                    };

                    setAlerts(prev => [newAlert, ...prev]);
                    window.dispatchEvent(new CustomEvent('axiom:new_alert', { detail: newAlert }));
                } catch (err) {
                    console.error("Failed to parse incoming SSE alert", err);
                }
            });

            eventSource.addEventListener('alert_update', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    setAlerts(prev => prev.map(a => a.id === data.alert_id ? { ...a, isRead: data.status === 'acknowledged' } : a));
                } catch (err) {
                    console.error("Failed to parse SSE alert update", err);
                }
            });

            return () => {
                eventSource.close();
            };
        }
    }, [isLoading]);

    const markAsRead = useCallback(async (id: string) => {
        // Optimistic UI update
        setAlerts(prev => prev.map(a => a.id === id ? { ...a, isRead: true } : a));

        if (!USE_MOCK) {
            try {
                await markAlertAsRead(id);
            } catch (e) {
                console.error("Failed to mark alert as read on server", e);
                // Revert optimistic if needed, simplified here
            }
        }
    }, []);

    const markAllAsRead = useCallback(async () => {
        setAlerts(prev => prev.map(a => ({ ...a, isRead: true })));

        if (!USE_MOCK) {
            try {
                await markAllAlertsAsRead();
            } catch (e) {
                console.error("Failed to mark all alerts as read on server", e);
            }
        }
    }, []);

    const getFilteredAlerts = useCallback((query: string, activeSeverity: Set<AlertSeverity>) => {
        return alerts.filter(a => {
            const matchesQuery = query === '' ||
                a.title.toLowerCase().includes(query.toLowerCase()) ||
                a.description.toLowerCase().includes(query.toLowerCase());
            const matchesSeverity = activeSeverity.has(a.severity);
            return matchesQuery && matchesSeverity;
        });
    }, [alerts]);

    return {
        alerts,
        isLoading,
        getFilteredAlerts,
        markAsRead,
        markAllAsRead
    };
}
