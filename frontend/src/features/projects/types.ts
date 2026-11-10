// Types for the project onboarding API (/api/projects/).
import type { Geometry } from "geojson";

export type Option = { value: string; label: string };
export type Country = { iso3: string; iso2: string; name: string; bbox: [number, number, number, number] };
export type BBox = [number, number, number, number];

export type Meta = {
  countries: Country[];
  sectors: Option[];
  themes: Option[];
  stages: Option[];
  hubs: Option[];
  statuses: Option[];
  levels: Option[];
  tiers: Option[];
  geo_roles: Option[];
  doc_types: Option[];
  area_methods: Option[];
  user: { signed_in: boolean; is_reviewer: boolean };
};

export type CRI = {
  code: string;
  name: string;
  unit: string;
  group_no: number;
  group_name: string;
  per_annum: boolean;
  sex_disaggregated: "yes" | "no" | "to_confirm";
  geida_role: string;
  candidate_module: string;
  notes: string;
};

export type AreaBrief = { method: string; area_km2: number; centroid: [number, number]; bbox: BBox };

export type ProjectItem = {
  code: string;
  title: string;
  country_iso3: string;
  country_name: string;
  sector: string;
  sector_label: string;
  stage: string;
  status: "draft" | "review" | "published";
  status_label: string;
  source: "manual" | "import" | "form";
  hub: string;
  owner: string;
  updated: string;
  area: AreaBrief | null;
  indicator_count: number | null;
  can_edit: boolean;
};

export type Indicator = {
  id?: number;
  level: string;
  statement: string;
  unit: string;
  cri: CRI | null;
  tier: string;
  baseline_value: number | null;
  baseline_year: number | null;
  target_value: number | null;
  target_year: number | null;
  means_of_verification: string;
  sex_disaggregated: boolean;
  geo_role: string;
  warnings?: string[];
  evidence?: { value: number | null; unit: string; instrument: string; role: string; reference_date: string; run: number } | null;
};

export type Doc = { id?: number; doc_type: string; title: string; url: string };
export type Component = { name: string; description: string };

export type Project = ProjectItem & {
  start_date: string | null;
  end_date: string | null;
  otl: string;
  location: string;
  themes: string[];
  components: Component[];
  source_info: Record<string, string>;
  review_comment: string;
  submitted_at: string | null;
  published_at: string | null;
  created: string;
  area: (AreaBrief & {
    notes: string[];
    source_name: string;
    admin_gids: string[];
    buffer: { lon?: number; lat?: number; km?: number };
    geometry: Geometry;
    updated: string;
  }) | null;
  indicators: Indicator[];
  documents: Doc[];
  geida_support: { cri: string; name: string; role: string; module: string; status: string }[];
  log: { action: string; user: string; detail: Record<string, unknown>; created: string }[];
  missing_to_submit: string[];
  permissions: {
    can_edit: boolean;
    can_review: boolean;
    can_submit: boolean;
    can_return: boolean;
    can_publish: boolean;
    can_delete: boolean;
  };
};

export type AreaPreview = {
  geometry: Geometry;
  area_km2: number;
  parts: number;
  bbox: BBox;
  inside_country: number | null;
  notes: string[];
  method: string;
  source_name?: string;
  features?: { index: number; name: string; geom_type: string; whole_world: boolean; selected: boolean }[];
};

export type ImportRow = {
  row: number;
  code: string;
  title: string;
  country: string;
  sector: string;
  stage: string;
  action: "new" | "update" | "error";
  errors: string[];
  warnings: string[];
  suggestion: { type: "country" | "point"; label: string } | null;
  boundary: "file" | "link" | "none";
  boundary_file?: string;
  documents: Doc[];
  source_info?: Record<string, string>;
};

// Analysis modules (/api/analysis/)
export type DatasetInfo = { id: string; title: string; kind: string; resolution: string; version: string; reference_date: string; citation: string; licence: string };
export type ModuleParam = { name: string; type: "number" | "choice"; default: number | string; label: string; min?: number; max?: number; choices?: { value: number | string; label: string }[] };
/** How a run's vector output is drawn (see backend/modules/README.md, "Vector styles"). */
export type VectorStyle = {
  color?: string; radius?: number; width?: number; opacity?: number;
  /** Swatch shape in the layer panel and legends (default: point). */
  shape?: "point" | "line" | "polygon";
  property?: string;
  classes?: { value: string | number; color: string; label: string; radius?: number; width?: number }[];
  steps?: { from: number; color: string; label: string }[];
};
export type ModuleCategory = { id: string; title: string; description: string; icon: string; order: number; modules: number };
export type ModuleInfo = {
  id: string; version: string; title: string; question: string; description: string; status: string; category: string;
  themes: string[]; phases: string[]; cri: { code: string; role: string }[];
  inputs: { name: string; required: boolean; label: string; type: string; dataset: DatasetInfo | null }[];
  parameters: ModuleParam[]; citations: string[];
  availability?: { status: "ready" | "needs_data" | "not_available"; reasons: string[] };
  cri_in_project?: string[];
};
export type RunOutput =
  | { type: "metric"; name: string; title: string; value: number | string; unit: string; note?: string }
  | { type: "table"; name: string; title: string; columns: { key: string; label: string; unit?: string }[]; rows: Record<string, string | number>[]; note?: string }
  | { type: "image"; name: string; title: string; file: string; bounds: [number, number, number, number]; legend: { label: string; color: string }[] }
  | { type: "vector"; name: string; title: string; file: string; style: VectorStyle }
  | { type: "file"; name: string; title: string; file: string };
export type Evidence = {
  id: number; run: number; cri: string; indicator: number | null; indicator_statement: string; phase: string; instrument: string;
  label: string; value: number | null; unit: string; reference_date: string; role: string; caveats: string;
  method: { module: string; version: string; params: Record<string, unknown> }; data: DatasetInfo[];
  status: "proposed" | "accepted" | "rejected"; reviewed_by: string; reviewed_at: string | null; created: string;
};
export type Run = {
  id: number; project: string; module: string; module_title: string; module_version: string; phase: string; instrument: string;
  params: Record<string, unknown>; status: "queued" | "running" | "done" | "failed" | "cancelled"; progress: number; error: string;
  created: string; started: string | null; finished: string | null; created_by: string; summary: string;
  outputs?: RunOutput[]; datasets?: DatasetInfo[]; log?: string; evidence?: Evidence[];
};
