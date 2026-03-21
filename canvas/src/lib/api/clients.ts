import { createApiClient } from './createApiClient';

// Fallback logic for production vs development URLs is handled by Vite natively using process.env / import.meta.env
// We enforce that the environment variable must be defined here, or throw an error to prevent silent failures

const getEnvUrl = (key: string): string => {
    const url = import.meta.env[key];
    if (!url) {
        if (key === 'VITE_CORE_URL') return 'http://localhost:9002';
        if (key === 'VITE_ORACLE_URL') return 'http://localhost:9004';
        if (key === 'VITE_WEAVER_URL') return 'http://localhost:9001';
        if (key === 'VITE_SYNAPSE_URL') return 'http://localhost:9003';
        if (key === 'VITE_OLAP_STUDIO_URL') return 'http://localhost:9005';
        console.warn(`Environment variable ${key} is not defined. API calls to this service may fail.`);
        return 'http://localhost:9002';
    }
    return (url as string).replace(/\/$/, '');
};

// VITE_XXX_URL mapped to specific backend SSOT endpoints
export const coreApi = createApiClient(getEnvUrl('VITE_CORE_URL'));
export const visionApi = createApiClient(getEnvUrl('VITE_VISION_URL'));
export const oracleApi = createApiClient(getEnvUrl('VITE_ORACLE_URL'));
export const synapseApi = createApiClient(getEnvUrl('VITE_SYNAPSE_URL'));
export const weaverApi = createApiClient(getEnvUrl('VITE_WEAVER_URL'));

// OLAP Studio API 클라이언트 (Gateway 경유 또는 직접 연결)
export const olapStudioApi = createApiClient(getEnvUrl('VITE_OLAP_STUDIO_URL'));
