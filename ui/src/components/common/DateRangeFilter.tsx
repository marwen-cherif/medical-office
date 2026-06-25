import * as React from "react";
import type { DateRange } from "react-day-picker";
import { CalendarDays } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { dateToIso, isoToDate, isoToFr } from "@/lib/format";

/**
 * Filtre de période : un champ unique qui ouvre, dès le clic, un calendrier de
 * plage sur deux mois (sélection début → fin). Bornes ISO `YYYY-MM-DD` incluses,
 * même contrat `{ from, to }` qu'auparavant (substituable sans toucher l'appelant).
 */
export function DateRangeFilter({
  from,
  to,
  onChange,
  className,
  align = "start",
}: {
  from: string;
  to: string;
  onChange: (range: { from: string; to: string }) => void;
  className?: string;
  align?: "start" | "center" | "end";
}) {
  const [open, setOpen] = React.useState(false);
  const selected: DateRange | undefined = from
    ? { from: isoToDate(from), to: isoToDate(to) }
    : undefined;

  const label =
    from && to
      ? `${isoToFr(from)} – ${isoToFr(to)}`
      : from
        ? `Depuis le ${isoToFr(from)}`
        : "Toute la période";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Filtrer par période"
          className={cn(
            "flex h-9 w-auto items-center gap-2 rounded-[var(--radius)] border border-line bg-white px-3 py-1 text-left text-sm shadow-sm transition-colors hover:bg-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy/40",
            className,
          )}
        >
          <CalendarDays className="size-4 shrink-0 text-muted" />
          <span className={cn("truncate", from ? "text-ink" : "text-muted")}>{label}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align={align} className="w-auto">
        <Calendar
          mode="range"
          autoFocus
          numberOfMonths={2}
          selected={selected}
          defaultMonth={isoToDate(from)}
          onSelect={(range) =>
            onChange({
              from: range?.from ? dateToIso(range.from) : "",
              to: range?.to ? dateToIso(range.to) : "",
            })
          }
        />
      </PopoverContent>
    </Popover>
  );
}
