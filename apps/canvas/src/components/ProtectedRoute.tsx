import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';

export const ProtectedRoute: React.FC = () => {
    // Simulating authentication lookup
    const isAuthenticated = localStorage.getItem('axiom_token') !== null || true; // Set to true for MVP mock flow

    if (!isAuthenticated) {
        console.warn("Unauthorized access blocked. Redirecting to login.");
        return <Navigate to="/login" replace />;
    }

    // If authenticated, render the child routes (Outlet)
    return <Outlet />;
};
