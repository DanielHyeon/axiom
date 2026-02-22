import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useWatchRules } from '@/features/watch/hooks/useWatchRules';
import type { WatchRuleCreatePayload } from '@/features/watch/types/watch';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { alertRuleFormSchema, EVENT_TYPES, type AlertRuleFormValues } from '../alertRuleFormSchema';

export function AlertRuleEditor() {
    const { rules, loading, error, refetch, addRule, removeRule, updateRuleById } = useWatchRules();
    const [editingId, setEditingId] = useState<string | null>(null);

    const { register, handleSubmit, reset, formState: { errors } } = useForm<AlertRuleFormValues>({
        resolver: zodResolver(alertRuleFormSchema),
        defaultValues: { name: '', event_type: EVENT_TYPES[0], active: true },
    });

    const onCreate = async (data: AlertRuleFormValues) => {
        const payload: WatchRuleCreatePayload = {
            name: data.name.trim(),
            event_type: data.event_type,
            active: data.active,
            definition: {},
        };
        try {
            await addRule(payload);
            reset({ name: '', event_type: EVENT_TYPES[0], active: true });
        } catch (err) {
            console.error('Create rule failed', err);
        }
    };

    const handleToggleActive = async (rule: { rule_id: string; active: boolean }) => {
        try {
            await updateRuleById(rule.rule_id, { active: !rule.active });
            if (editingId === rule.rule_id) setEditingId(null);
        } catch (err) {
            console.error('Update rule failed', err);
        }
    };

    const handleDelete = async (ruleId: string) => {
        try {
            await removeRule(ruleId);
            if (editingId === ruleId) setEditingId(null);
        } catch (err) {
            console.error('Delete rule failed', err);
        }
    };

    if (loading) {
        return <div className="p-4 text-neutral-400 text-sm">규칙 로딩 중...</div>;
    }
    if (error) {
        return (
            <div className="p-4">
                <p className="text-red-400 text-sm mb-2">규칙 목록을 불러올 수 없습니다. {error.message}</p>
                <button
                    type="button"
                    onClick={() => refetch()}
                    className="text-sm px-3 py-1.5 rounded border border-neutral-600 text-neutral-300 hover:bg-neutral-800"
                >
                    다시 시도
                </button>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-4">
            <form onSubmit={handleSubmit(onCreate)} className="flex flex-wrap items-end gap-3 p-4 border border-neutral-800 rounded-lg bg-[#1a1a1a]">
                <div className="flex flex-col gap-1">
                    <label className="text-xs text-neutral-400">이름</label>
                    <Input
                        placeholder="규칙 이름"
                        className="w-48 bg-neutral-900 border-neutral-800 text-neutral-200"
                        {...register('name')}
                    />
                    {errors.name && <span className="text-xs text-red-400">{errors.name.message}</span>}
                </div>
                <div className="flex flex-col gap-1">
                    <label className="text-xs text-neutral-400">이벤트 유형</label>
                    <select
                        aria-label="이벤트 유형"
                        className="h-9 w-48 rounded border border-neutral-800 bg-neutral-900 text-neutral-200 px-2 text-sm"
                        {...register('event_type')}
                    >
                        {EVENT_TYPES.map((t) => (
                            <option key={t} value={t}>{t}</option>
                        ))}
                    </select>
                </div>
                <div className="flex items-center gap-2">
                    <input
                        type="checkbox"
                        id="active-new"
                        className="rounded border-neutral-600"
                        {...register('active', { setValueAs: (v) => v === true || v === 'on' })}
                    />
                    <label htmlFor="active-new" className="text-sm text-neutral-400">활성</label>
                </div>
                <Button type="submit" variant="default" size="sm">추가</Button>
            </form>

            <ul className="space-y-2">
                {rules.map((rule) => (
                    <li
                        key={rule.rule_id}
                        className="flex items-center justify-between p-3 border border-neutral-800 rounded-lg bg-[#1e1e1e]"
                    >
                        <div className="flex flex-col gap-0.5">
                            <span className="text-sm font-medium text-neutral-200">{rule.name}</span>
                            <span className="text-xs text-neutral-500">{rule.event_type}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => handleToggleActive(rule)}
                                className="text-xs px-2 py-1 rounded border border-neutral-700 text-neutral-300 hover:bg-neutral-800"
                            >
                                {rule.active ? '비활성화' : '활성화'}
                            </button>
                            <button
                                type="button"
                                onClick={() => handleDelete(rule.rule_id)}
                                className="text-xs px-2 py-1 rounded border border-red-900/50 text-red-400 hover:bg-red-950/30"
                            >
                                삭제
                            </button>
                        </div>
                    </li>
                ))}
            </ul>
            {rules.length === 0 && (
                <p className="text-sm text-neutral-500 p-4">등록된 알림 규칙이 없습니다.</p>
            )}
        </div>
    );
}
