import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/stores/authStore';
import { ROUTES } from '@/lib/routes/routes';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';

/**
 * 사용자 이메일에서 이니셜 2글자를 추출한다.
 * 예: "daniel.kim@axiom.co" → "DK", "admin@local.axiom" → "AD"
 */
function getInitials(email: string): string {
  // '@' 앞 부분을 '.' 또는 '_' 또는 '-' 로 분리
  const local = email.split('@')[0] ?? '';
  const parts = local.split(/[._-]/).filter(Boolean);

  if (parts.length >= 2) {
    // 이름·성이 구분된 경우: 각 첫 글자
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  // 단일 단어: 첫 두 글자
  return local.slice(0, 2).toUpperCase();
}

export function UserMenu() {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  if (!user) {
    return (
      <Link to={ROUTES.AUTH.LOGIN}>
        <Button variant="ghost" size="sm">{t('userMenu.login')}</Button>
      </Link>
    );
  }

  const initials = getInitials(user.email || user.id);

  return (
    <Popover>
      <PopoverTrigger asChild>
        {/* 28x28 원형 아바타 — Sora 10px 볼드 이니셜 */}
        <button
          type="button"
          className="size-7 rounded-full bg-muted flex items-center justify-center font-heading text-[10px] font-semibold text-muted-foreground cursor-pointer hover:ring-2 hover:ring-ring transition-shadow"
          aria-label={user.email || user.id}
        >
          {initials}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-56">
        <div className="flex flex-col gap-2">
          <div className="text-sm text-muted-foreground truncate" title={user.email || ''}>
            {user.email || user.id}
          </div>
          <div className="text-xs text-foreground/60">{user.role}</div>
          <hr className="border-border" />
          <Link to={ROUTES.SETTINGS_USERS}>
            <Button variant="ghost" size="sm" className="w-full justify-start">
              {t('userMenu.settings')}
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start text-destructive hover:text-destructive"
            onClick={logout}
          >
            {t('userMenu.logout')}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
