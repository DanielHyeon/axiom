// features/process-designer/components/canvas/ConnectionStatusBanner.tsx
// WS 연결 끊김 경고 배너 (설계 §11.1)

interface ConnectionStatusBannerProps {
 connected: boolean;
 /** WS 협업이 활성화된 경우에만 배너 표시 */
 wsEnabled?: boolean;
}

export function ConnectionStatusBanner({ connected, wsEnabled = false }: ConnectionStatusBannerProps) {
 // WS가 비활성화되었거나 연결된 상태면 배너 숨김
 if (!wsEnabled || connected) return null;

 return (
 <div className="bg-amber-900/50 border-b border-amber-700 px-3 py-1.5 text-xs text-amber-300">
 실시간 동기화 연결이 끊어졌습니다. 재연결 중...
 </div>
 );
}
