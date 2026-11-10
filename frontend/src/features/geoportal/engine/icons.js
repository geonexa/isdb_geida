// Icons for HTML the engine builds itself (layer cards, tool lists, saved areas).
// Static markup uses lucide-react; these <i data-lucide="..."> placeholders are swapped by createIcons.
import {
  ChevronDown, ChevronRight, ChevronUp, Download, Droplets, Eye, EyeOff, Grid3x3, Info, Mountain,
  Scan, Spline, Trash2, X, createIcons,
} from "lucide";

const ICONS = { ChevronDown, ChevronRight, ChevronUp, Download, Droplets, Eye, EyeOff, Grid3x3, Info, Mountain, Scan, Spline, Trash2, X };

export function renderIcons(root) {
  createIcons({ icons: ICONS, root: root || document });
}
