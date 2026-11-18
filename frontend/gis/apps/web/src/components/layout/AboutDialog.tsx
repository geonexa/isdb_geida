import {
  Button,
  type ButtonProps,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@geolibre/ui";
import { Info, Map } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

// GEIDA: the About dialog describes GEIDA's Analytics workspace and credits GeoLibre, without GeoLibre's version,
// update check or links (the status bar keeps its "Built on GeoLibre" credit link).

interface AboutDialogProps {
  /** Kept for GeoLibre's call sites; GEIDA has no update check. */
  checkForUpdatesRequest?: number;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  renderTrigger?: boolean;
  buttonClassName?: string;
  buttonSize?: ButtonProps["size"];
  iconClassName?: string;
  showLabels?: boolean;
}

export function AboutDialog({
  open,
  onOpenChange,
  renderTrigger = true,
  buttonClassName,
  buttonSize = "sm",
  iconClassName,
  showLabels = true,
}: AboutDialogProps) {
  const { t } = useTranslation();
  const [internalOpen, setInternalOpen] = useState(false);
  const dialogOpen = open ?? internalOpen;

  const handleOpenChange = (nextOpen: boolean) => {
    setInternalOpen(nextOpen);
    onOpenChange?.(nextOpen);
  };

  return (
    <Dialog open={dialogOpen} onOpenChange={handleOpenChange}>
      {renderTrigger ? (
        <DialogTrigger asChild>
          <Button
            className={buttonClassName}
            variant="ghost"
            size={buttonSize}
            aria-label={t("about.trigger")}
          >
            <Info className={iconClassName ?? "h-3.5 w-3.5 sm:me-1"} />
            {showLabels ? <span className="hidden sm:inline">{t("about.trigger")}</span> : null}
          </Button>
        </DialogTrigger>
      ) : null}
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Map className="h-5 w-5 text-primary" />
            {t("about.geidaTitle", { defaultValue: "About GEIDA Analytics" })}
          </DialogTitle>
          <DialogDescription>
            {t("about.geidaSubtitle", { defaultValue: "IsDB Geoinformatics Data Platform" })}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <p className="leading-relaxed text-foreground">
            {t("about.geidaDescription", {
              defaultValue:
                "Analytics is GEIDA's workspace for working further with a project's data: open the layers from its " +
                "analyses and Toolbox runs, add your own files and map services, run processing tools in the browser, " +
                "compare dates and make maps for reports.",
            })}
          </p>
          <p className="border-t pt-3 text-xs text-muted-foreground">
            {t("about.geidaCredit", {
              defaultValue:
                "Built on GeoLibre, the open-source web GIS by Qiusheng Wu and contributors (MIT licence).",
            })}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
