import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, type ReactNode } from "react";

import { api } from "@/shared/api/client";
import type { User } from "@/shared/api/types";

type AuthValue = {
  user: User | null;
  loading: boolean;
  setUser: (u: User | null) => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  // /me also sets the CSRF cookie the API needs for POST requests.
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ user: User | null }>("/api/auth/me/"),
    staleTime: 5 * 60_000,
  });
  const setUser = useCallback((u: User | null) => qc.setQueryData(["me"], { user: u }), [qc]);
  const signOut = useCallback(async () => {
    await api("/api/auth/sign-out/", { method: "POST" });
    setUser(null);
  }, [setUser]);
  return (
    <AuthContext.Provider value={{ user: me.data?.user ?? null, loading: me.isPending, setUser, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const v = useContext(AuthContext);
  if (!v) throw new Error("useAuth must be used inside <AuthProvider>");
  return v;
}
