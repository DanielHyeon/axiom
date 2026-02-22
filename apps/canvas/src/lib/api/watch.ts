import { coreApi } from './clients';
import type { Alert } from '@/features/watch/types/watch';

export const fetchAlerts = async (): Promise<Alert[]> => {
    const response = await coreApi.get('/api/v1/watches/alerts');
    const payload = (response as { data?: unknown })?.data ?? response;
    const normalized = (payload as { data?: unknown })?.data ?? payload;
    return Array.isArray(normalized) ? (normalized as Alert[]) : [];
};

export const markAlertAsRead = async (id: string): Promise<void> => {
    await coreApi.put(`/api/v1/watches/alerts/${id}/acknowledge`);
};

export const markAllAlertsAsRead = async (): Promise<void> => {
    await coreApi.put('/api/v1/watches/alerts/read-all');
};
