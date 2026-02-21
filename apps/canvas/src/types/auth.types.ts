export type UserRole = 'admin' | 'manager' | 'attorney' | 'analyst' | 'engineer' | 'staff' | 'viewer';
export type CaseRole = 'owner' | 'reviewer' | 'viewer';

export interface AccessTokenPayload {
    sub: string;
    email: string;
    role: UserRole;
    tenant_id: string;
    permissions: string[];
    case_roles: Record<string, CaseRole>;
    iat: number;
    exp: number;
}

export interface User {
    id: string;
    email: string;
    role: UserRole;
    tenantId: string;
    permissions: string[];
    caseRoles: Record<string, CaseRole>;
}

export interface AuthResponse {
    accessToken: string;
    refreshToken: string;
    user: User;
}
