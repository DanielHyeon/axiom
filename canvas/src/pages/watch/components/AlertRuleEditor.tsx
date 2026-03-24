import { useState } from 'react';
import { toast } from 'sonner';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useWatchRules } from '@/features/watch/hooks/useWatchRules';
import type { WatchRuleCreatePayload } from '@/features/watch/types/watch';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { alertRuleFormSchema, EVENT_TYPES, type AlertRuleFormValues } from '../alertRuleFormSchema';
import { useTranslation } from 'react-i18next';

export function AlertRuleEditor() {
  const { t } = useTranslation();
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
 toast.success(t('watchPage.alertRuleCreated'));
 } catch (err) {
 console.error('Create rule failed', err);
 toast.error(t('watchPage.alertRuleCreateFailed'));
 }
 };

 const handleToggleActive = async (rule: { rule_id: string; active: boolean }) => {
 try {
 await updateRuleById(rule.rule_id, { active: !rule.active });
 if (editingId === rule.rule_id) setEditingId(null);
 toast.success(t('watchPage.alertRuleUpdated'));
 } catch (err) {
 console.error('Update rule failed', err);
 toast.error(t('watchPage.alertRuleUpdateFailed'));
 }
 };

 const handleDelete = async (ruleId: string) => {
 try {
 await removeRule(ruleId);
 if (editingId === ruleId) setEditingId(null);
 toast.success(t('watchPage.alertRuleDeleted'));
 } catch (err) {
 console.error('Delete rule failed', err);
 toast.error(t('watchPage.alertRuleDeleteFailed'));
 }
 };

 if (loading) {
 return <div className="p-4 text-muted-foreground text-sm">{t('watchPage.msg4681254b')}</div>;
 }
 if (error) {
 return (
 <div className="p-4">
 <p className="text-destructive text-sm mb-2">{t('watchPage.ruleLoadError')}</p>
 <button
 type="button"
 onClick={() => refetch()}
 className="text-sm px-3 py-1.5 rounded border border-border text-foreground/80 hover:bg-muted"
 >
 {t('datasource.erd.retryBtn')}
 </button>
 </div>
 );
 }

 return (
 <div className="flex flex-col gap-4">
 <form onSubmit={handleSubmit(onCreate)} className="flex flex-wrap items-end gap-3 p-4 border border-border rounded-lg bg-popover">
 <div className="flex flex-col gap-1">
 <label className="text-xs text-muted-foreground">{t('mvExt.colName')}</label>
 <Input
 placeholder={t('cepExt.ruleName')}
 className="w-48 bg-card border-border text-foreground"
 {...register('name')}
 />
 {errors.name && <span className="text-xs text-destructive">{errors.name.message}</span>}
 </div>
 <div className="flex flex-col gap-1">
 <label className="text-xs text-muted-foreground">{t('workflowEditor.trigger.eventType')}</label>
 <select
 aria-label={t('workflowEditor.trigger.eventType')}
 className="h-9 w-48 rounded border border-border bg-card text-foreground px-2 text-sm"
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
 className="rounded border-border"
 {...register('active', { setValueAs: (v) => v === true || v === 'on' })}
 />
 <label htmlFor="active-new" className="text-sm text-muted-foreground">{t('cepExt.colEnabled')}</label>
 </div>
 <Button type="submit" variant="default" size="sm">{t('common.add')}</Button>
 </form>

 <ul className="space-y-2">
 {rules.map((rule) => (
 <li
 key={rule.rule_id}
 className="flex items-center justify-between p-3 border border-border rounded-lg bg-card"
 >
 <div className="flex flex-col gap-0.5">
 <span className="text-sm font-medium text-foreground">{rule.name}</span>
 <span className="text-xs text-foreground0">{rule.event_type}</span>
 </div>
 <div className="flex items-center gap-2">
 <button
 type="button"
 onClick={() => handleToggleActive(rule)}
 className="text-xs px-2 py-1 rounded border border-border text-foreground/80 hover:bg-muted"
 >
 {rule.active ? t('semanticCatalogExt.deactivate') : t('semanticCatalogExt.activate')}
 </button>
 <button
 type="button"
 onClick={() => handleDelete(rule.rule_id)}
 className="text-xs px-2 py-1 rounded border border-red-900/50 text-destructive hover:bg-red-950/30"
 >
 {t('ingestionExt.delete')}
 </button>
 </div>
 </li>
 ))}
 </ul>
 {rules.length === 0 && (
 <p className="text-sm text-foreground0 p-4">{t('watchPage.noAlertrule')}</p>
 )}
 </div>
 );
}
