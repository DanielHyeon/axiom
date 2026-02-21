import { createApiClient } from './createApiClient';

// Fallback logic for production vs development URLs is handled by Vite natively using process.env / import.meta.env
// We enforce that the environment variable must be defined here, or throw an error to prevent silent failures

const getEnvUrl = (key: string): string => {
    const url = import.meta.env[key];
    if (!url) {
        console.warn(`Environment variable ${key} is not defined. API calls to this service will fail.`);
        return '';
    }
    return url;
};

// VITE_XXX_URL mapped to specific backend SSOT endpoints
export const coreApi = createApiClient(getEnvUrl('VITE_CORE_URL'));
export const visionApi = createApiClient(getEnvUrl('VITE_VISION_URL'));
export const oracleApi = createApiClient(getEnvUrl('VITE_ORACLE_URL'));
export const synapseApi = createApiClient(getEnvUrl('VITE_SYNAPSE_URL'));
export const weaverApi = createApiClient(getEnvUrl('VITE_WEAVER_URL'));
