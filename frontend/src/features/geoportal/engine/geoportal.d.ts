export function initGeoportal(cfg: {
  catalog: unknown;
  basemaps: unknown;
  areas: { signedIn: boolean; api: string; countries: string };
}): { destroy: () => void };
