import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/shared/api/client";
import type { Evidence, ModuleCategory, ModuleInfo, Run } from "@/features/projects/types";

export type Phase = { value: string; label: string; instrument: string };
export const ACTIVE = new Set(["queued", "running"]);
export const fileUrl = (run: number, file: string) => `/api/analysis/runs/${run}/files/${encodeURIComponent(file)}`;
export const fmtNum = (v: number | string | null | undefined) =>
  v == null ? "—" : typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 1 }) : v;

/** Project stage (PCN…PPER) -> GEIDA workspace phase. */
export const STAGE_PHASE: Record<string, string> = {
  PCN: "preparation", PPRR: "preparation", PAD: "preparation", PIASR: "implementation", PCR: "completion", PPER: "completion",
};

export function useModules(code: string) {
  return useQuery({
    queryKey: ["modules", code],
    queryFn: () => api<{ modules: ModuleInfo[]; categories: ModuleCategory[]; phases: Phase[] }>(`/api/analysis/modules/?project=${code}`),
  });
}

export function useRuns(code: string) {
  return useQuery({
    queryKey: ["runs", code],
    queryFn: () => api<{ runs: Run[] }>(`/api/analysis/runs/?project=${code}`).then((d) => d.runs),
    refetchInterval: (q) => (q.state.data?.some((r) => ACTIVE.has(r.status)) ? 2500 : false),
  });
}

export function useRun(id: number | null) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => api<{ run: Run }>(`/api/analysis/runs/${id}/`).then((d) => d.run),
    enabled: id != null,
    refetchInterval: (q) => (q.state.data && ACTIVE.has(q.state.data.status) ? 2500 : false),
  });
}

export function useEvidence(code: string) {
  return useQuery({
    queryKey: ["evidence", code],
    queryFn: () => api<{ evidence: Evidence[] }>(`/api/analysis/evidence/?project=${code}`).then((d) => d.evidence),
  });
}

/** Accept/reject evidence and refresh everything that shows it. */
export function useReviewEvidence(code: string) {
  const qc = useQueryClient();
  return async (e: Evidence, action: "accept" | "reject") => {
    await api(`/api/analysis/evidence/${e.id}/${action}/`, { method: "POST", body: {} });
    qc.invalidateQueries({ queryKey: ["evidence", code] });
    qc.invalidateQueries({ queryKey: ["run", e.run] });
    qc.invalidateQueries({ queryKey: ["project", code] });
  };
}
