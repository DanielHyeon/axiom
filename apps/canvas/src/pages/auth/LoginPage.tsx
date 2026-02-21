import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

export function LoginPage() {
    const navigate = useNavigate();
    const login = useAuthStore((state) => state.login);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const handleLogin = (e: React.FormEvent) => {
        e.preventDefault();
        // Mock login
        login('mock-access-token', 'mock-refresh-token', {
            id: 'usr-1',
            email,
            tenantId: 'tnt-1',
            role: 'admin',
            caseRoles: {},
            permissions: ['case:read', 'document:write'],
        });
        navigate('/');
    };

    return (
        <div className="flex h-screen w-full items-center justify-center bg-neutral-950 px-4">
            <div className="w-full max-w-sm rounded-lg border border-neutral-800 bg-neutral-900 p-8 shadow-xl">
                <div className="mb-8 text-center">
                    <h1 className="text-2xl font-bold tracking-tight text-white mb-2">Axiom Canvas</h1>
                    <p className="text-sm text-neutral-400">Enter your credentials to access the system</p>
                </div>

                <form onSubmit={handleLogin} className="space-y-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-neutral-300" htmlFor="email">Email</label>
                        <input
                            id="email"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="name@example.com"
                            required
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-neutral-300" htmlFor="password">Password</label>
                        <input
                            id="password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="••••••••"
                            required
                        />
                    </div>
                    <button
                        type="submit"
                        className="w-full rounded-md bg-white text-black hover:bg-neutral-200 px-4 py-2 text-sm font-medium transition-colors mt-2"
                    >
                        Sign In
                    </button>
                </form>
            </div>
        </div>
    );
}
