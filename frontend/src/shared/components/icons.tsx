import {
  BookOpen, Database, FileText, FolderKanban, GraduationCap, LayoutDashboard, LifeBuoy, Map as MapIcon,
  ScanSearch, type LucideIcon, type LucideProps,
} from "lucide-react";

// Icons named in the backend's section list (apps/core/modules.py).
const ICONS: Record<string, LucideIcon> = {
  map: MapIcon,
  "scan-search": ScanSearch,
  "layout-dashboard": LayoutDashboard,
  "folder-kanban": FolderKanban,
  "file-text": FileText,
  database: Database,
  "graduation-cap": GraduationCap,
  "book-open": BookOpen,
  "life-buoy": LifeBuoy,
};

export function NamedIcon({ name, ...props }: { name: string } & LucideProps) {
  const I = ICONS[name] ?? MapIcon;
  return <I aria-hidden="true" {...props} />;
}
