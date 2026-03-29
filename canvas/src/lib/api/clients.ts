import { createApiClient } from './createApiClient';

// ─── 서비스별 기본 프록시 경로 ───
// .env.development 또는 .env.docker에서 VITE_*_URL이 설정되지 않은 경우,
// Vite/Nginx 프록시 경유 상대 경로를 기본값으로 사용한다.
// 이렇게 하면 개발(Vite proxy)·Docker(Nginx proxy) 모두 동일하게 동작한다.
const PROXY_DEFAULTS: Record<string, string> = {
    VITE_CORE_URL: '/proxy/core',
    VITE_WEAVER_URL: '/proxy/weaver',
    VITE_ORACLE_URL: '/proxy/oracle',
    VITE_SYNAPSE_URL: '/proxy/synapse',
    VITE_VISION_URL: '/proxy/vision',
    VITE_OLAP_STUDIO_URL: '/api/gateway/olap',
};

const getEnvUrl = (key: string): string => {
    const url = import.meta.env[key];
    if (!url) {
        const fallback = PROXY_DEFAULTS[key];
        if (fallback) return fallback;
        console.warn(`Environment variable ${key} is not defined. API calls to this service may fail.`);
        return '/proxy/core';
    }
    return (url as string).replace(/\/$/, '');
};

// VITE_XXX_URL → axios 인스턴스 (SSOT)
export const coreApi = createApiClient(getEnvUrl('VITE_CORE_URL'));
export const visionApi = createApiClient(getEnvUrl('VITE_VISION_URL'));
export const oracleApi = createApiClient(getEnvUrl('VITE_ORACLE_URL'));
export const synapseApi = createApiClient(getEnvUrl('VITE_SYNAPSE_URL'));
export const weaverApi = createApiClient(getEnvUrl('VITE_WEAVER_URL'));

// OLAP Studio API 클라이언트 (Gateway 경유)
export const olapStudioApi = createApiClient(getEnvUrl('VITE_OLAP_STUDIO_URL'));
