import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Module, SiteContent, User } from "@/shared/api/types";

export function useSite() {
  return useQuery({ queryKey: ["site"], queryFn: () => api<SiteContent>("/api/site/"), staleTime: Infinity });
}

/** Sections the user may see: those with `roles` need a matching role. */
export function forUser(modules: Module[] | undefined, user: User | null): Module[] {
  return (modules ?? []).filter((m) => !m.roles?.length || (!!user && m.roles.some((r) => r === "analyst" && user.is_analyst)));
}
