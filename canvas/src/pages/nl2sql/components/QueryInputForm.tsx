/**
 * QueryInputForm — 질문 입력 폼 + SQL 미리보기
 *
 * 사용자가 자연어 질문을 입력하고 실행 버튼을 누르는 폼이다.
 * HIL(사람-개입) 활성화 시 입력이 비활성화된다.
 */
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslation } from 'react-i18next';
import { ArrowRight, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';
import { nl2sqlPromptSchema, type Nl2sqlPromptFormValues } from '../nl2sqlFormSchema';

interface QueryInputFormProps {
  /** 질문 제출 핸들러 */
  onSubmit: (question: string) => Promise<void>;
  /** 로딩 중인지 여부 */
  loading: boolean;
  /** 데이터소스가 선택되었는지 */
  datasourceId: string;
  /** HIL 요청이 활성화되었는지 */
  hilActive: boolean;
  /** 생성된 SQL (미리보기용) */
  generatedSql: string | null;
  /** 폼 prompt 값을 외부에서 설정할 수 있도록 노출 */
  setPromptRef?: (setter: (value: string) => void) => void;
}

export function QueryInputForm({
  onSubmit,
  loading,
  datasourceId,
  hilActive,
  generatedSql,
  setPromptRef,
}: QueryInputFormProps) {
  const { t } = useTranslation();

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<Nl2sqlPromptFormValues>({
    resolver: zodResolver(nl2sqlPromptSchema),
    defaultValues: { prompt: '' },
  });

  const promptValue = watch('prompt');

  // 외부에서 prompt 값을 설정할 수 있도록 콜백 노출
  // (예제 질문 클릭, 히스토리 선택 등)
  if (setPromptRef) {
    setPromptRef((value: string) => setValue('prompt', value));
  }

  const handleFormSubmit = async (data: Nl2sqlPromptFormValues) => {
    const question = data.prompt.trim();
    if (!question) return;
    reset({ prompt: '' });
    await onSubmit(question);
  };

  return (
    <>
      {/* 질문 입력 폼 */}
      <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-3">
        <div className="flex items-end gap-3">
          <div
            className={cn(
              'flex-1 flex items-center gap-3 px-5 py-3.5 border border-[#E5E5E5] rounded',
              hilActive && 'opacity-50 pointer-events-none',
            )}
          >
            <MessageSquare className="h-4 w-4 text-foreground/60 shrink-0" />
            <input
              type="text"
              placeholder={t('nl2sql.placeholder')}
              className="flex-1 bg-transparent text-[13px] text-black placeholder:text-foreground/60 font-[IBM_Plex_Mono] outline-none"
              disabled={hilActive}
              {...register('prompt')}
            />
          </div>
          <button
            type="submit"
            disabled={loading || !promptValue?.trim() || !datasourceId || hilActive}
            className="flex items-center gap-2 px-4 py-2.5 bg-destructive text-white text-[12px] font-medium font-[Sora] rounded disabled:opacity-50 hover:bg-red-700 transition-colors shrink-0"
          >
            <ArrowRight className="h-3.5 w-3.5" />
            {t('nl2sql.run')}
          </button>
        </div>
        {errors.prompt && <p className="text-xs text-destructive">{errors.prompt.message}</p>}
      </form>

      {/* SQL 미리보기 */}
      {generatedSql && (
        <div className="bg-[#F5F5F5] rounded py-4 px-5 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold text-foreground/60 font-[IBM_Plex_Mono] uppercase tracking-[1px]">
              {t('nl2sql.generatedSql')}
            </span>
          </div>
          <pre className="text-[12px] text-black font-[IBM_Plex_Mono] whitespace-pre-wrap break-words">
            {generatedSql}
          </pre>
        </div>
      )}
    </>
  );
}
