import { useState, useCallback, useEffect, useMemo } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';
import { useRole } from '@/shared/hooks/useRole';
import {
  LayoutDashboard,
  MessageSquareText,
  ChartBar,
  Lightbulb,
  Database,
  Eye,
  Settings,
  Menu,
  X,
} from 'lucide-react';

/* ──────────────────────────────────────────────────
 * 네비게이션 아이콘 정의
 * - .pen 디자인 파일 기준 7개 아이콘 (6개 네비 + 1개 설정)
 * - 각 아이콘은 64x64 영역 중앙 정렬, 아이콘 크기 18px
 * ────────────────────────────────────────────────── */

/** 네비게이션 항목 하나를 표현하는 타입 */
type NavItem = {
  /** 클릭하면 이동할 경로 */
  to: string;
  /** lucide-react 아이콘 컴포넌트 */
  icon: React.ComponentType<{ className?: string }>;
  /** i18n 번역 키 (툴팁에 표시) */
  labelKey: string;
  /** 이 아이콘이 활성화될 경로 접두사 목록 */
  activePrefixes: string[];
};

/** 디자인 파일 기준 6개 네비게이션 아이콘 */
const navItems: NavItem[] = [
  {
    to: ROUTES.DASHBOARD,
    icon: LayoutDashboard,
    labelKey: 'sidebar.dashboard',
    // 대시보드 + 케이스 상세 페이지에서 활성화
    activePrefixes: ['/dashboard', '/cases'],
  },
  {
    to: ROUTES.ANALYSIS.NL2SQL,
    icon: MessageSquareText,
    labelKey: 'sidebar.nl2sql',
    // NL2SQL 채팅 페이지에서만 활성화
    activePrefixes: ['/analysis/nl2sql'],
  },
  {
    to: ROUTES.ANALYSIS.OLAP,
    icon: ChartBar,
    labelKey: 'sidebar.olapPivot',
    // OLAP 피벗 + OLAP Studio에서 활성화
    activePrefixes: ['/analysis/olap'],
  },
  {
    to: ROUTES.ANALYSIS.INSIGHT,
    icon: Lightbulb,
    labelKey: 'sidebar.insight',
    // 인사이트 + What-if 시뮬레이션에서 활성화
    activePrefixes: ['/analysis/insight', '/analysis/whatif'],
  },
  {
    to: ROUTES.DATA.DATASOURCES,
    icon: Database,
    labelKey: 'sidebar.data',
    // /data 하위 모든 페이지에서 활성화
    activePrefixes: ['/data'],
  },
  {
    to: ROUTES.WATCH,
    icon: Eye,
    labelKey: 'sidebar.watch',
    // 모니터링 + 프로세스 디자이너에서 활성화
    activePrefixes: ['/watch', '/process-designer'],
  },
];

/**
 * 현재 경로가 주어진 접두사 목록 중 하나와 매칭되는지 확인하는 함수
 * - 접두사가 정확히 일치하거나 / 뒤에 추가 경로가 있으면 활성화
 */
function isPathActive(pathname: string, prefixes: string[]): boolean {
  return prefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(prefix + '/'),
  );
}

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const isAdmin = useRole(['admin']);
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  /* 모바일 메뉴 토글 */
  const toggleMobile = useCallback(() => setMobileOpen((v) => !v), []);

  /* 페이지 이동 시 모바일 메뉴 자동 닫기 */
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  /* 설정 페이지 활성화 여부 (admin 전용) */
  const isSettingsActive = useMemo(
    () => isPathActive(location.pathname, ['/settings']),
    [location.pathname],
  );

  return (
    <>
      {/* ── 모바일 햄버거 버튼 ── */}
      <button
        type="button"
        onClick={toggleMobile}
        className="fixed top-3 left-3 z-50 flex items-center justify-center w-10 h-10 rounded-lg bg-sidebar text-sidebar-foreground shadow-md md:hidden"
        aria-label={mobileOpen ? t('sidebar.close') : t('sidebar.open')}
      >
        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* ── 모바일 오버레이 (배경 어둡게) ── */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── 사이드바 본체 ── */}
      <aside
        aria-label="Main navigation"
        className={`
          fixed inset-y-0 left-0 z-40 w-16 shrink-0
          flex flex-col justify-between bg-sidebar
          transition-transform duration-200 ease-in-out
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
          md:relative md:translate-x-0
        `}
      >
        {/* ── 상단: 로고 + 네비게이션 아이콘 6개 ── */}
        <div className="flex flex-col items-center pt-8">
          {/* 로고: "A" 글자, Sora 폰트, 16px, bold, 흰색 */}
          <div className="flex items-center justify-center w-16 h-16 shrink-0">
            <span className="text-base font-bold font-heading text-white">
              A
            </span>
          </div>

          {/* 네비게이션 아이콘 목록 */}
          <nav className="flex flex-col w-full">
            {navItems.map((item) => {
              /* 현재 경로와 접두사 비교해서 활성 상태 결정 */
              const active = isPathActive(location.pathname, item.activePrefixes);

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  aria-label={t(item.labelKey)}
                  aria-current={active ? 'page' : undefined}
                  className={`
                    relative flex items-center justify-center w-16 h-16
                    group transition-colors
                    ${active ? 'text-white' : 'text-sidebar-foreground hover:text-white'}
                  `}
                >
                  {/* 활성 표시: 왼쪽 3px 오렌지 보더 */}
                  {active && (
                    <div className="absolute inset-y-0 left-0 w-[3px] bg-primary" />
                  )}

                  {/* 아이콘: 18x18px */}
                  <item.icon className="h-[18px] w-[18px]" />

                  {/* 툴팁: 마우스 호버 시 오른쪽에 표시 */}
                  <div
                    className="
                      absolute left-full ml-2 px-2 py-1
                      bg-popover text-popover-foreground text-xs rounded
                      opacity-0 group-hover:opacity-100 group-focus-within:opacity-100
                      pointer-events-none whitespace-nowrap z-50 transition-opacity
                    "
                    role="tooltip"
                  >
                    {t(item.labelKey)}
                  </div>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* ── 하단: 설정 아이콘 (admin 전용) ── */}
        <div className="flex flex-col items-center pb-4">
          {isAdmin && (
            <NavLink
              to={ROUTES.SETTINGS}
              aria-label={t('sidebar.settings')}
              aria-current={isSettingsActive ? 'page' : undefined}
              className={`
                relative flex items-center justify-center w-16 h-16
                group transition-colors
                ${isSettingsActive ? 'text-white' : 'text-sidebar-foreground hover:text-white'}
              `}
            >
              {/* 활성 표시: 왼쪽 3px 오렌지 보더 */}
              {isSettingsActive && (
                <div className="absolute inset-y-0 left-0 w-[3px] bg-primary" />
              )}

              <Settings className="h-[18px] w-[18px]" />

              {/* 툴팁 */}
              <div
                className="
                  absolute left-full ml-2 px-2 py-1
                  bg-popover text-popover-foreground text-xs rounded
                  opacity-0 group-hover:opacity-100 group-focus-within:opacity-100
                  pointer-events-none whitespace-nowrap z-50 transition-opacity
                "
                role="tooltip"
              >
                {t('sidebar.settings')}
              </div>
            </NavLink>
          )}
        </div>
      </aside>
    </>
  );
};
