import type { UserRole } from '@/types/auth.types';

const ROLE_LABEL: Record<UserRole, string> = {
  admin: '관리자',
  manager: '매니저',
  attorney: '담당자',
  analyst: '분석가',
  engineer: '엔지니어',
  staff: '스태프',
  viewer: '뷰어',
};

interface RoleGreetingProps {
  userName?: string | null;
  role?: UserRole | null;
  workCount?: number;
}

export function RoleGreeting({ userName, role, workCount = 0 }: RoleGreetingProps) {
  const name = userName ?? '사용자';
  const roleText = role ? ROLE_LABEL[role] : '';
  return (
    <div className="mb-4">
      <h1 className="text-2xl font-bold tracking-tight text-white">
        안녕하세요, {name}님.
      </h1>
      {roleText && (
        <p className="mt-1 text-sm text-neutral-400">
          {roleText} · 대기 업무 {workCount}건
        </p>
      )}
    </div>
  );
}
