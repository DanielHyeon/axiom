import { z } from 'zod';

export const EVENT_TYPES = [
  'DEADLINE_APPROACHING',
  'CASH_LOW',
  'DATA_REGISTERED',
  'ANOMALY_INDICATOR',
  'ISSUE_RATIO_HIGH',
] as const;

export const alertRuleFormSchema = z.object({
  name: z.string().refine((s) => s.trim().length > 0, '규칙 이름을 입력하세요.'),
  event_type: z.enum(EVENT_TYPES),
  active: z.boolean(),
});

export type AlertRuleFormValues = z.infer<typeof alertRuleFormSchema>;
