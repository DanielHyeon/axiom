import { Link } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { ROUTES } from '@/lib/routes/routes';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';

export function UserMenu() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  if (!user) {
    return (
      <Link to={ROUTES.AUTH.LOGIN}>
        <Button variant="ghost" size="sm">로그인</Button>
      </Link>
    );
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="text-gray-700 hover:bg-gray-100">
          {user.email || user.id}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-56">
        <div className="flex flex-col gap-2">
          <div className="text-sm text-neutral-600 truncate" title={user.email || ''}>
            {user.email || user.id}
          </div>
          <div className="text-xs text-neutral-500">{user.role}</div>
          <hr className="border-gray-200" />
          <Link to={ROUTES.SETTINGS_USERS}>
            <Button variant="ghost" size="sm" className="w-full justify-start">
              설정
            </Button>
          </Link>
          <Button variant="ghost" size="sm" className="w-full justify-start text-red-600 hover:text-red-700" onClick={logout}>
            로그아웃
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
