import { z } from 'zod';

export const nl2sqlPromptSchema = z.object({
  prompt: z.string().refine((s) => s.trim().length > 0, '질문을 입력하세요.'),
});

export type Nl2sqlPromptFormValues = z.infer<typeof nl2sqlPromptSchema>;
