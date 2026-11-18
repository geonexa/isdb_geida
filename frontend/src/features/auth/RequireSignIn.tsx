import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/features/auth/AuthContext";

/**
 * Pages for signed-in users only (projects): visitors are sent to sign in and come back here afterwards.
 * The API refuses project data to visitors too (apps/projects/access.py); this only avoids an empty page.
 */
export function RequireSignIn({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  if (!user) return <Navigate to={`/accounts/sign-in?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  return <>{children}</>;
}
