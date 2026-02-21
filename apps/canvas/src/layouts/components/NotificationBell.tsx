import { Bell } from 'lucide-react';
import { useNotificationBell } from '../../features/watch/hooks/useNotificationBell';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';

export function NotificationBell() {
    const { unreadCount, recentAlerts, clearBadge } = useNotificationBell();

    return (
        <Popover onOpenChange={(open: boolean) => { if (open) clearBadge() }}>
            <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" className="relative text-neutral-400 hover:text-white">
                    <Bell size={20} />
                    {unreadCount > 0 && (
                        <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                        </span>
                    )}
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-80 p-0 bg-[#161616] border-neutral-800 text-neutral-200" align="end" sideOffset={8}>
                <div className="flex items-center justify-between p-4 border-b border-neutral-800 bg-[#1a1a1a]">
                    <h4 className="font-semibold text-sm">알림</h4>
                    {unreadCount > 0 && (
                        <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full font-medium">
                            {unreadCount} 새로운 알림
                        </span>
                    )}
                </div>
                <div className="max-h-80 overflow-y-auto">
                    {recentAlerts.length === 0 ? (
                        <div className="p-4 text-sm text-neutral-500 text-center py-8">
                            새로운 알림이 없습니다.
                        </div>
                    ) : (
                        <div className="flex flex-col">
                            {recentAlerts.map(alert => (
                                <Link
                                    key={alert.id}
                                    to={`/watch?alert=${alert.id}`}
                                    className="p-4 border-b border-neutral-800/50 hover:bg-neutral-800/50 transition-colors flex flex-col gap-1"
                                >
                                    <div className="flex justify-between items-start gap-2">
                                        <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${alert.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                                            alert.severity === 'warning' ? 'bg-amber-500/20 text-amber-400' :
                                                'bg-blue-500/20 text-blue-400'
                                            }`}>
                                            {alert.severity.toUpperCase()}
                                        </span>
                                        <span className="text-[10px] text-neutral-500 whitespace-nowrap">
                                            {new Date(alert.timestamp).toLocaleTimeString()}
                                        </span>
                                    </div>
                                    <h5 className="text-sm font-medium text-neutral-200 mt-1">{alert.title}</h5>
                                    <p className="text-xs text-neutral-400 line-clamp-2 leading-relaxed">
                                        {alert.description}
                                    </p>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
                <div className="p-2 border-t border-neutral-800 bg-[#1a1a1a]">
                    <Link to="/watch">
                        <Button variant="ghost" className="w-full text-xs text-neutral-400 hover:text-white h-8">
                            모든 알림 보기
                        </Button>
                    </Link>
                </div>
            </PopoverContent>
        </Popover>
    );
}
