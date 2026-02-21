import { AxiosError } from 'axios';

/** Canvas 전역 에러 클래스 */
export class AppError extends Error {
    public readonly code: string;
    public readonly messageText: string;
    public readonly status: number;
    public readonly details?: Record<string, string[]>;
    public readonly originalError?: unknown;

    constructor(
        code: string,
        messageText: string,
        status: number,
        details?: Record<string, string[]>,
        originalError?: unknown,
    ) {
        super(messageText);
        this.name = 'AppError';
        this.code = code;
        this.messageText = messageText;
        this.status = status;
        this.details = details;
        this.originalError = originalError;
    }

    get isAuthError(): boolean {
        return this.status === 401 || this.status === 403;
    }

    get isValidationError(): boolean {
        return this.status === 422;
    }

    get isServerError(): boolean {
        return this.status >= 500;
    }

    get isNetworkError(): boolean {
        return this.code === 'NETWORK_ERROR';
    }

    /** 사용자에게 표시할 메시지 */
    get userMessage(): string {
        if (this.isNetworkError) return '네트워크 연결을 확인해 주세요.';

        switch (this.status) {
            case 401: return '인증이 만료되었습니다. 다시 로그인해 주세요.';
            case 403: return '이 작업에 대한 권한이 없습니다.';
            case 404: return '요청한 리소스를 찾을 수 없습니다.';
            case 409: return '데이터 충돌이 발생했습니다. 새로고침 후 다시 시도해 주세요.';
            case 422: return '입력 데이터가 올바르지 않습니다.';
            case 429: return '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.';
            default: return this.status >= 500
                ? '서버에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.'
                : this.message;
        }
    }
}

export function normalizeError(error: AxiosError): AppError {
    // 네트워크 에러 (서버 응답 없음)
    if (!error.response) {
        return new AppError(
            'NETWORK_ERROR',
            'Network Error',
            0,
            undefined,
            error,
        );
    }

    const { status, data } = error.response;
    const apiError = data as { error?: { code: string; message: string; details?: Record<string, string[]> } };

    return new AppError(
        apiError?.error?.code || `HTTP_${status} `,
        apiError?.error?.message || getDefaultMessage(status),
        status,
        apiError?.error?.details,
        error,
    );
}

function getDefaultMessage(status: number): string {
    const messages: Record<number, string> = {
        400: '잘못된 요청입니다.',
        401: '인증이 만료되었습니다.',
        403: '권한이 없습니다.',
        404: '리소스를 찾을 수 없습니다.',
        409: '데이터 충돌',
        422: '검증 오류',
        429: '요청 너무 많음',
        500: '서버 오류',
        502: 'Bad Gateway',
        503: 'Service Unavailable',
    };
    return messages[status] || '알 수 없는 오류가 발생했습니다.';
}
