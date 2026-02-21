import { Outlet } from 'react-router-dom';

export const AuthLayout = () => {
    return (
        <div className="min-h-screen bg-neutral-900 flex items-center justify-center text-white">
            <main className="w-full max-w-md p-6 bg-neutral-800 rounded-lg shadow-xl">
                <h1 className="text-2xl font-bold mb-6 text-center">Axiom Canvas</h1>
                <Outlet />
            </main>
        </div>
    );
};
