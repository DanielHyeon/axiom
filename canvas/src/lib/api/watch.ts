import { coreApi } from './clients';
import type { Alert, WatchRule, WatchRuleCreatePayload, WatchRuleUpdatePayload } from '@/features/watch/types/watch';

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

// --- Watch rules (CEP) CRUD ---
export const listRules = async (): Promise<WatchRule[]> => {
    const response = await coreApi.get('/api/v1/watches/rules');
    const payload = (response as { data?: unknown })?.data ?? response;
    const list = (payload as { data?: WatchRule[] })?.data ?? payload;
    return Array.isArray(list) ? list : [];
};

export const getRule = async (ruleId: string): Promise<WatchRule> => {
    const response = await coreApi.get(`/api/v1/watches/rules/${ruleId}`);
    return response as unknown as WatchRule;
};

export const createRule = async (body: WatchRuleCreatePayload): Promise<{ rule_id: string }> => {
    const response = await coreApi.post('/api/v1/watches/rules', body);
    return response as unknown as { rule_id: string };
};

export const updateRule = async (ruleId: string, body: WatchRuleUpdatePayload): Promise<WatchRule> => {
    const response = await coreApi.put(`/api/v1/watches/rules/${ruleId}`, body);
    return response as unknown as WatchRule;
};

export const deleteRule = async (ruleId: string): Promise<void> => {
    await coreApi.delete(`/api/v1/watches/rules/${ruleId}`);
};
