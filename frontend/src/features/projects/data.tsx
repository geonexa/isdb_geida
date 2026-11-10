import { useQuery, useQueryClient } from "@tanstack/react-query";
import "@/features/projects/projects.css";

import { api } from "@/shared/api/client";
import type { Meta, Project } from "@/features/projects/types";

export function useMeta() {
  return useQuery({ queryKey: ["projects-meta"], queryFn: () => api<Meta>("/api/projects/meta/"), staleTime: 10 * 60_000 });
}

export function useProject(code?: string) {
  return useQuery({
    queryKey: ["project", code],
    queryFn: () => api<{ project: Project }>(`/api/projects/${code}/`).then((d) => d.project),
    enabled: !!code,
  });
}

/** Store a fresh project (from any API response) in the query cache. */
export function useSetProject() {
  const qc = useQueryClient();
  return (p: Project) => {
    qc.setQueryData(["project", p.code], p);
    qc.invalidateQueries({ queryKey: ["projects"] });
  };
}

export const label = (opts: { value: string; label: string }[] | undefined, v: string) =>
  opts?.find((o) => o.value === v)?.label ?? v;

export const km2 = (n: number) =>
  n >= 100 ? `${Math.round(n).toLocaleString()} km²` : `${n.toLocaleString(undefined, { maximumFractionDigits: 2 })} km²`;

export const STEP_NAMES = ["Identity", "Area", "Themes", "Results", "Documents"] as const;

export const MISSING_LABELS: Record<string, string> = {
  code: "Project code",
  title: "Title",
  country_iso3: "Country",
  sector: "Sector",
  stage: "Cycle stage",
  area: "Area of influence",
};

export function StatusChip({ status, text }: { status: string; text?: string }) {
  return <span className={`pchip pchip-${status}`}>{text ?? { draft: "Draft", review: "Under review", published: "Published" }[status] ?? status}</span>;
}
