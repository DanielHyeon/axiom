/**
 * 서비스별 헬스 체크 (Core / Vision / Oracle).
 * 헬스 엔드포인트는 인증 없이 호출 가능하다고 가정.
 */

const getBaseUrl = (key: string): string => {
    const url = import.meta.env[key];
    if (!url) return key === 'VITE_CORE_URL' ? 'http://localhost:8000' : 'http://localhost:8000';
    return (url as string).replace(/\/$/, '');
};

async function checkOne(
    name: string,
    url: string,
    signal: AbortSignal
): Promise<{ name: string; status: 'up' | 'down'; error?: string }> {
    try {
        const res = await fetch(url, { signal, method: 'GET' });
        if (!res.ok) {
            return { name, status: 'down', error: `HTTP ${res.status}` };
        }
        const data = await res.json().catch(() => ({}));
        const statusVal = (data?.status ?? data?.checks ?? '').toString().toLowerCase();
        const healthy = res.ok && (statusVal === 'healthy' || statusVal === 'ok' || statusVal === '');
        return { name, status: healthy ? 'up' : 'down' };
    } catch (e) {
        return {
            name,
            status: 'down',
            error: e instanceof Error ? e.message : String(e)
        };
    }
}

export type ServiceStatus = { name: string; status: 'up' | 'down'; error?: string };

const CORE_URL = () => getBaseUrl('VITE_CORE_URL') + '/api/v1/health/live';
const VISION_URL = () => getBaseUrl('VITE_VISION_URL') + '/health';
const ORACLE_URL = () => getBaseUrl('VITE_ORACLE_URL') + '/health';

export async function checkServiceHealth(abort?: AbortSignal): Promise<ServiceStatus[]> {
    return Promise.all([
        checkOne('Core', CORE_URL(), abort ?? new AbortController().signal),
        checkOne('Vision', VISION_URL(), abort ?? new AbortController().signal),
        checkOne('Oracle', ORACLE_URL(), abort ?? new AbortController().signal)
    ]);
}
