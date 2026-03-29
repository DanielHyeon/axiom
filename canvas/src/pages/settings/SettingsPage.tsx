/**
 * SettingsPage — 설정 페이지 레이아웃 (디자인 리뉴얼)
 *
 * .pen 디자인 매칭:
 * - 수평 분할 레이아웃 (좌측 Nav 220px + 우측 Content fill)
 * - 좌측 Nav: right border, 24px/16px 패딩, 4px 갭
 *   - 항목: 36px 높이, 12px 수평 패딩, 8px 갭, 6px radius
 *   - 활성: bg #F5F5F5 + 검정 텍스트, 비활성: #5E5E5E 텍스트
 *   - 아이콘: monitor / users / shield / scroll / sliders-horizontal / message-circle
 * - 우측 Content: 32px/48px 패딩, Outlet에 하위 페이지 렌더링
 *
 * React Router nested routes 사용 (기존 routeConfig 재활용)
 */

import React from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Monitor,
  Users,
  Shield,
  ScrollText,
  SlidersHorizontal,
  MessageCircle,
} from 'lucide-react';
import { ROUTES } from '@/lib/routes/routes';

// 설정 내비게이션 항목 정의
interface SettingsNavItem {
  to: string;
  labelKey: string;
  icon: React.ElementType;
}

const NAV_ITEMS: SettingsNavItem[] = [
  { to: ROUTES.SETTINGS_SYSTEM, labelKey: 'settings.tabs.system', icon: Monitor },
  { to: ROUTES.SETTINGS_USERS, labelKey: 'settings.tabs.users', icon: Users },
  { to: ROUTES.SETTINGS_SECURITY, labelKey: 'settings.tabs.security', icon: Shield },
  { to: ROUTES.SETTINGS_LOGS, labelKey: 'settings.tabs.logs', icon: ScrollText },
  { to: ROUTES.SETTINGS_CONFIG, labelKey: 'settings.tabs.config', icon: SlidersHorizontal },
  { to: ROUTES.SETTINGS_FEEDBACK, labelKey: 'settings.tabs.feedback', icon: MessageCircle },
];

export const SettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const location = useLocation();

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── 좌측: Settings Nav (220px, right border) ── */}
      <nav
        className="flex flex-col gap-1 w-[220px] shrink-0 border-r border-border px-4 py-6"
        role="navigation"
        aria-label={t('settings.menuLabel', '설정 메뉴')}
      >
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          // NavLink 대신 직접 active 판별 (중첩 라우트에서 더 정확)
          const isActive = location.pathname.startsWith(item.to);

          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={[
                'flex items-center gap-2 h-9 px-3 rounded-md text-[13px] transition-colors',
                isActive
                  ? 'bg-muted text-foreground font-medium'
                  : 'text-text-secondary hover:bg-muted/60 hover:text-foreground',
              ].join(' ')}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span>{t(item.labelKey)}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* ── 우측: Settings Content (fill, 32px/48px 패딩) ── */}
      <div className="flex-1 min-w-0 overflow-y-auto px-12 py-8">
        <Outlet />
      </div>
    </div>
  );
};
