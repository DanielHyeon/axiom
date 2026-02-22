import React from 'react';
import { NotificationBell } from './NotificationBell';
import { UserMenu } from './UserMenu';

export function Header() {
  return (
    <header className="h-12 shrink-0 border-b border-gray-200 bg-white flex items-center justify-end gap-2 px-4">
      <NotificationBell />
      <UserMenu />
    </header>
  );
}
