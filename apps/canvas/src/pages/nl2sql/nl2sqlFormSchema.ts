import { z } from 'zod';

export const nl2sqlPromptSchema = z.object({
  prompt: z
    .string()
    .min(1, '질문을 입력하세요.')
    .max(2000, '질문은 2000자 이내로 입력해주세요.'),
});

export type Nl2sqlPromptFormValues = z.infer<typeof nl2sqlPromptSchema>;
