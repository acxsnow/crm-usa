import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";

export function ProtectedRoute({ children, requiredPermission }: { children: ReactNode; requiredPermission?: string }) {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();
  const location = useLocation();

  if (isLoading) return <div className="loading-screen">Loading...</div>;

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <div className="no-permission">You don't have permission to view this page.</div>;
  }

  return <>{children}</>;
}
