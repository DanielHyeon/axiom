export interface ApiResponse<T = unknown> {
    success: boolean;
    data: T;
    meta?: {
        page?: number;
        pageSize?: number;
        total?: number;
        totalPages?: number;
    };
    error?: {
        code: string;
        message: string;
        details?: Record<string, string[]>;
    };
}
