import { NotificationBell } from './NotificationBell';
import { UserMenu } from './UserMenu';
import { ThemeToggle } from './ThemeToggle';
import { LocaleToggle } from './LocaleToggle';

export function Header() {
  return (
    <header className="glass-header relative z-10 h-14 shrink-0 flex items-center justify-end gap-3 px-5">
      <LocaleToggle />
      <ThemeToggle />
      <NotificationBell />
      <UserMenu />
    </header>
  );
}
