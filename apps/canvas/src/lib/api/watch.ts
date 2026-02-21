import { coreApi } from './clients';
import type { Alert } from '@/features/watch/types/watch';

export const fetchAlerts = async (): Promise<Alert[]> => {
    const response = await coreApi.get('/api/v1/watches/alerts');
    return response.data;
};

export const markAlertAsRead = async (id: string): Promise<void> => {
    await coreApi.put(`/api/v1/watches/alerts/${id}/acknowledge`);
};

export const markAllAlertsAsRead = async (): Promise<void> => {
    await coreApi.put('/api/v1/watches/alerts/read-all');
};
