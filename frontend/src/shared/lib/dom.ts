import { useEffect } from "react";

const SUFFIX = "IsDB Geoinformatics Data Platform";

export function useTitle(title?: string) {
  useEffect(() => {
    document.title = title ? `${title} | ${SUFFIX}` : `GEIDA | ${SUFFIX}`;
  }, [title]);
}

/** Page-level body class (page-home, page-map, page-auth), as the old templates set it. */
export function useBodyClass(cls: string) {
  useEffect(() => {
    if (!cls) return;
    document.body.classList.add(cls);
    return () => document.body.classList.remove(cls);
  }, [cls]);
}
