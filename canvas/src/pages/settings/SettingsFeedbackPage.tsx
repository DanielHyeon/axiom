/**
 * SettingsFeedbackPage — 피드백 통계 대시보드 페이지.
 *
 * Settings > 피드백 탭에서 표시된다.
 * admin 전용 (RoleGuard에 의해 Settings 하위 전체가 admin 전용).
 */
import { FeedbackDashboard } from '@/features/feedback/components/FeedbackDashboard';

export function SettingsFeedbackPage() {
  return <FeedbackDashboard />;
}
