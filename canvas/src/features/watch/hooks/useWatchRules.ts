import { useState, useEffect, useCallback } from 'react';
import type { WatchRule, WatchRuleCreatePayload, WatchRuleUpdatePayload } from '../types/watch';
import { listRules, getRule, createRule, updateRule, deleteRule } from '@/lib/api/watch';

export function useWatchRules() {
    const [rules, setRules] = useState<WatchRule[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    const fetchRules = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await listRules();
            setRules(Array.isArray(data) ? data : []);
        } catch (e) {
            setError(e instanceof Error ? e : new Error(String(e)));
            setRules([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchRules();
    }, [fetchRules]);

    const addRule = useCallback(async (payload: WatchRuleCreatePayload) => {
        await createRule(payload);
        await fetchRules();
    }, [fetchRules]);

    const updateRuleById = useCallback(async (ruleId: string, payload: WatchRuleUpdatePayload) => {
        await updateRule(ruleId, payload);
        await fetchRules();
    }, [fetchRules]);

    const removeRule = useCallback(async (ruleId: string) => {
        await deleteRule(ruleId);
        await fetchRules();
    }, [fetchRules]);

    const getRuleById = useCallback(async (ruleId: string): Promise<WatchRule | null> => {
        try {
            return await getRule(ruleId);
        } catch {
            return null;
        }
    }, []);

    return {
        rules,
        loading,
        error,
        refetch: fetchRules,
        addRule,
        updateRuleById,
        removeRule,
        getRuleById
    };
}
