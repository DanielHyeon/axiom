/**
 * SettingsSystemPage — 시스템 설정 (디자인 리뉴얼)
 *
 * .pen 디자인 매칭:
 * - 타이틀: "System Settings" Sora 18px semibold
 * - 폼 필드: 480px max-width, 수직 스택, 24px 갭
 *   - Label: Geist 12px secondary(#5E5E5E) + Input: 40px 높이, 흰 배경, border, 8px radius
 *   - Select: 동일 스타일 + chevron-down 아이콘
 * - Save 버튼: 120px width, 40px height, primary fill(#FF8400), 8px radius
 *
 * 백엔드 연동: GET/PUT /proxy/core/settings + 기존 health API 재사용
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, Loader2 } from 'lucide-react';
import { checkServiceHealth, type ServiceStatus } from '@/lib/api/health';
import { getCoreReadiness, type CoreReadinessResponse } from '@/lib/api/settingsApi';
import { toast } from 'sonner';

/** 시스템 설정 폼 상태 */
interface SystemSettings {
  platformName: string;
  defaultLanguage: string;
  semanticGuardMode: string;
}

export const SettingsSystemPage: React.FC = () => {
  const { t } = useTranslation();

  // 서비스 상태
  const [serviceStatuses, setServiceStatuses] = useState<ServiceStatus[]>([]);
  const [, setCoreReadiness] = useState<CoreReadinessResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // 폼 상태
  const [form, setForm] = useState<SystemSettings>({
    platformName: 'Axiom',
    defaultLanguage: 'ko',
    semanticGuardMode: 'warn',
  });
  const [saving, setSaving] = useState(false);

  /** 서비스 상태 + 설정 로드 */
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statuses, readiness] = await Promise.all([
        checkServiceHealth(),
        getCoreReadiness().catch(() => null),
      ]);
      setServiceStatuses(statuses);
      setCoreReadiness(readiness);
    } catch {
      // 실패 시 빈 상태 유지
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /** 폼 필드 변경 핸들러 */
  const updateField = <K extends keyof SystemSettings>(key: K, value: SystemSettings[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  /** 저장 핸들러 */
  const handleSave = async () => {
    setSaving(true);
    try {
      // TODO: PUT /proxy/core/settings API 연동
      await new Promise((r) => setTimeout(r, 500));
      toast.success(t('settings.saved', '설정이 저장되었습니다.'));
    } catch {
      toast.error(t('settings.saveFailed', '설정 저장에 실패했습니다.'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-text-placeholder" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* 섹션 타이틀 — Sora 18px semibold */}
      <h2 className="text-lg font-semibold text-foreground font-heading">
        {t('settingsSystem.title', 'System Settings')}
      </h2>

      {/* 폼 필드 영역 — max-w-[480px], 24px 갭 */}
      <div className="flex flex-col gap-6 max-w-[480px]">
        {/* Platform Name — 텍스트 입력 */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="settings-platform-name" className="text-xs text-text-secondary">
            {t('settingsSystem.platformName', 'Platform Name')}
          </label>
          <input
            id="settings-platform-name"
            type="text"
            value={form.platformName}
            onChange={(e) => updateField('platformName', e.target.value)}
            className="h-10 w-full rounded-lg bg-card border border-border px-3.5 text-[13px] text-foreground outline-none focus:border-primary transition-colors"
          />
        </div>

        {/* Default Language — 셀렉트 */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="settings-default-language" className="text-xs text-text-secondary">
            {t('settingsSystem.defaultLanguage', 'Default Language')}
          </label>
          <div className="relative">
            <select
              id="settings-default-language"
              value={form.defaultLanguage}
              onChange={(e) => updateField('defaultLanguage', e.target.value)}
              className="h-10 w-full appearance-none rounded-lg bg-card border border-border px-3.5 pr-10 text-[13px] text-foreground outline-none focus:border-primary transition-colors"
            >
              <option value="ko">Korean (ko)</option>
              <option value="en">English (en)</option>
            </select>
            <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-secondary pointer-events-none" />
          </div>
        </div>

        {/* Semantic Guard Mode — 셀렉트 */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="settings-guard-mode" className="text-xs text-text-secondary">
            {t('settingsSystem.semanticGuardMode', 'Semantic Guard Mode')}
          </label>
          <div className="relative">
            <select
              id="settings-guard-mode"
              value={form.semanticGuardMode}
              onChange={(e) => updateField('semanticGuardMode', e.target.value)}
              className="h-10 w-full appearance-none rounded-lg bg-card border border-border px-3.5 pr-10 text-[13px] font-mono font-medium text-primary outline-none focus:border-primary transition-colors"
            >
              <option value="log_only">log_only</option>
              <option value="warn">warn</option>
              <option value="enforce">enforce</option>
            </select>
            <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-secondary pointer-events-none" />
          </div>
        </div>

        {/* Save 버튼 — 120px, 40px, primary, 8px radius */}
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="flex items-center justify-center w-[120px] h-10 rounded-lg bg-primary text-[13px] font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-60 transition-colors"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            t('common.save', 'Save')
          )}
        </button>
      </div>

      {/* 서비스 상태 섹션 (기존 기능 유지, 디자인 통합) */}
      {serviceStatuses.length > 0 && (
        <div className="flex flex-col gap-3 max-w-[480px] mt-4">
          <h3 className="text-xs font-medium text-text-secondary">
            {t('settingsSystem.serviceStatus', 'Service Status')}
          </h3>
          <div className="rounded-lg border border-border divide-y divide-border">
            {serviceStatuses.map((s) => (
              <div
                key={s.name}
                className="flex items-center justify-between px-3.5 py-2.5"
              >
                <span className="text-[13px] text-foreground">{s.name}</span>
                <span
                  className={
                    s.status === 'up'
                      ? 'text-xs font-medium text-accent-green'
                      : 'text-xs font-medium text-destructive'
                  }
                >
                  {s.status === 'up' ? t('common.normal', '정상') : t('common.abnormal', '비정상')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
