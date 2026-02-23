import React from 'react';
import { NotificationBell } from './NotificationBell';
import { UserMenu } from './UserMenu';
import { ThemeToggle } from './ThemeToggle';
import { LocaleToggle } from './LocaleToggle';

export function Header() {
  return (
    <header className="h-12 shrink-0 border-b border-gray-200 bg-white dark:border-neutral-800 dark:bg-neutral-900 flex items-center justify-end gap-2 px-4">
      <LocaleToggle />
      <ThemeToggle />
      <NotificationBell />
      <UserMenu />
    </header>
  );
}
