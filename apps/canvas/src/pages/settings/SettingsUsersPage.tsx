import React, { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { getCurrentUser } from '@/lib/api/usersApi';

/** 설정 > 사용자. GET /api/v1/users/me로 서버와 동기화 후 표시. 사용자 목록은 백엔드 API 연동 후 확장. */
export const SettingsUsersPage: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  useEffect(() => {
    getCurrentUser().then(setUser).catch(() => {});
  }, [setUser]);

  if (!user) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">사용자</h2>
        <p className="text-sm text-neutral-500">로그인된 사용자 정보가 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">사용자</h2>
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-neutral-700">현재 사용자</h3>
        <ul className="border border-neutral-200 rounded divide-y divide-neutral-200">
          <li className="px-4 py-2 flex justify-between">
            <span className="text-neutral-500">ID</span>
            <span className="font-mono text-sm">{user.id}</span>
          </li>
          <li className="px-4 py-2 flex justify-between">
            <span className="text-neutral-500">이메일</span>
            <span>{user.email}</span>
          </li>
          <li className="px-4 py-2 flex justify-between">
            <span className="text-neutral-500">역할</span>
            <span>{user.role}</span>
          </li>
          <li className="px-4 py-2 flex justify-between">
            <span className="text-neutral-500">테넌트</span>
            <span className="font-mono text-sm">{user.tenantId}</span>
          </li>
          {user.permissions?.length > 0 && (
            <li className="px-4 py-2 flex justify-between gap-4">
              <span className="text-neutral-500 shrink-0">권한</span>
              <span className="text-sm text-right break-all">
                {user.permissions.join(', ')}
              </span>
            </li>
          )}
          {user.caseRoles && Object.keys(user.caseRoles).length > 0 && (
            <li className="px-4 py-2 flex justify-between gap-4">
              <span className="text-neutral-500 shrink-0">케이스 역할</span>
              <span className="text-sm text-right">
                {Object.entries(user.caseRoles)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(', ')}
              </span>
            </li>
          )}
        </ul>
      </div>
      <p className="text-sm text-neutral-500">
        사용자 목록·추가/수정은 백엔드 사용자 API 연동 후 제공됩니다.
      </p>
    </div>
  );
};
