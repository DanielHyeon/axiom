import { Outlet } from 'react-router-dom';

export const AuthLayout = () => {
 return (
 <div className="min-h-screen bg-card flex items-center justify-center text-primary-foreground px-4 sm:px-6">
 <main className="w-full max-w-sm sm:max-w-md p-4 sm:p-6 bg-muted rounded-lg shadow-xl">
 <h1 className="text-xl sm:text-2xl font-bold mb-4 sm:mb-6 text-center">Axiom Canvas</h1>
 <Outlet />
 </main>
 </div>
 );
};
