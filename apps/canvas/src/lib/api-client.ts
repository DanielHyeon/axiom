import axios from 'axios';
import type { AxiosInstance, AxiosError } from 'axios';

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
        // In actual implementation, fetch from secure Session store
        const mockToken = localStorage.getItem('axiom_token') || 'mock_token_admin';
        const tenantId = localStorage.getItem('tenant_id') || '12345678-1234-5678-1234-567812345678';

        config.headers['Authorization'] = `Bearer ${mockToken}`;
        config.headers['X-Tenant-Id'] = tenantId;

        return config;
    },
    (error) => Promise.reject(error)
);

// Response Interceptor: Catch application boundaries
apiClient.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        if (error.response) {
            if (error.response.status === 401) {
                console.error("401 Unauthorized: Redirecting to Login");
                // window.location.href = '/login';
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
