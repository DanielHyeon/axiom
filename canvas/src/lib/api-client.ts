import axios from 'axios';
import type { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/authStore';

// Configure overarching Backend communication routes
export const apiClient: AxiosInstance = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request Interceptor: Inject JWT and Multi-tenant bindings
apiClient.interceptors.request.use(
    (config) => {
        const state = useAuthStore.getState();
        const token = state.accessToken;
        const tenantId = state.user?.tenantId || '12345678-1234-5678-1234-567812345678';

        if (token) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }
        config.headers['X-Tenant-Id'] = tenantId;

        return config;
    },
    (error) => Promise.reject(error)
);

// Response Interceptor: Catch application boundaries
apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
        if (error.response) {
            if (error.response.status === 401) {
                if (original && !original._retry && !original.url?.includes('/auth/')) {
                    original._retry = true;
                    try {
                        const newToken = await useAuthStore.getState().refreshAccessToken();
                        if (original.headers) {
                            original.headers.Authorization = `Bearer ${newToken}`;
                        }
                        return apiClient(original);
                    } catch {
                        return Promise.reject(error);
                    }
                }
            } else if (error.response.status === 403) {
                console.error("403 Forbidden: Insufficient clearance for action");
            } else if (error.response.status >= 500) {
                console.error("500 Internal Server Error: Microservice dependency failed");
            }
        } else if (error.request) {
            console.error("Network Error: No response received from target gateway.");
        }
        return Promise.reject(error);
    }
);
