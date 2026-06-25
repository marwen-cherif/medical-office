import * as React from "react";
import { CalendarDays } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { dateToIso, isoToDate, isoToFr } from "@/lib/format";

export type DatePickerProps = {
  /** Date sélectionnée au format ISO `YYYY-MM-DD` (chaîne vide = aucune). */
  value: string;
  /** Appelé avec la nouvelle date ISO (chaîne vide si effacée). */
  onChange: (iso: string) => void;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  /** Alignement du calendrier sous le champ. */
  align?: "start" | "center" | "end";
  /** Menus déroulants mois/année (utile pour une date de naissance). */
  dropdown?: boolean;
  /** Bornes d'années quand `dropdown` est actif (défaut : 1920 → année courante). */
  fromYear?: number;
  toYear?: number;
  /**
   * Mode modal du popover. Indispensable (et activé par défaut) quand le sélecteur
   * vit dans un `Dialog` : sans lui, le piège à focus du Dialog reprend la main et
   * referme le calendrier aussitôt ouvert.
   */
  modal?: boolean;
};

/**
 * Sélecteur de date unique : un champ d'apparence `Input` qui ouvre un calendrier
 * (popover) dès le clic. Renvoie/consomme des dates ISO `YYYY-MM-DD`. Remplaçant
 * direct des `<input type="date">` natifs, réutilisé dans toute l'application.
 */
export function DatePicker({
  value,
  onChange,
  id,
  placeholder = "JJ/MM/AAAA",
  disabled,
  className,
  align = "start",
  dropdown,
  fromYear = 1920,
  toYear,
  modal = true,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false);
  const selected = isoToDate(value);
  const endYear = toYear ?? new Date().getFullYear();

  return (
    <Popover open={open} onOpenChange={setOpen} modal={modal}>
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
          disabled={disabled}
          className={cn(
            "flex h-9 w-full items-center gap-2 rounded-[var(--radius)] border border-line bg-white px-3 py-1 text-left text-sm shadow-sm transition-colors hover:bg-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/40 disabled:cursor-not-allowed disabled:opacity-50",
            className,
          )}
        >
          <CalendarDays className="size-4 shrink-0 text-muted" />
          <span className={cn("truncate", value ? "text-ink" : "text-muted")}>
            {value ? isoToFr(value) : placeholder}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align={align} className="w-auto">
        <Calendar
          mode="single"
          autoFocus
          selected={selected}
          defaultMonth={selected}
          captionLayout={dropdown ? "dropdown" : "label"}
          startMonth={dropdown ? new Date(fromYear, 0) : undefined}
          endMonth={dropdown ? new Date(endYear, 11) : undefined}
          onSelect={(day) => {
            onChange(day ? dateToIso(day) : "");
            setOpen(false);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
