import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";
import { DayPicker } from "react-day-picker";
import { fr } from "date-fns/locale";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

export type CalendarProps = React.ComponentProps<typeof DayPicker>;

/**
 * Calendrier shadcn adossé à react-day-picker v9, habillé avec la palette du
 * cabinet (marine + turquoise) et la locale française (semaine débutant le lundi).
 * Sert de base aux sélecteurs `DatePicker` (date simple) et `DateRangeFilter` (plage).
 */
export function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
  return (
    <DayPicker
      locale={fr}
      weekStartsOn={1}
      showOutsideDays={showOutsideDays}
      className={cn("select-none", className)}
      classNames={{
        months: "relative flex flex-col gap-4 sm:flex-row",
        month: "flex flex-col gap-3",
        month_caption: "relative flex h-8 items-center justify-center px-9",
        caption_label: "flex items-center gap-1 text-sm font-medium capitalize text-ink",
        dropdowns: "flex items-center justify-center gap-1.5",
        dropdown_root:
          "relative inline-flex items-center rounded-md border border-line bg-white px-2 py-1 hover:bg-bg focus-within:ring-2 focus-within:ring-navy/40",
        dropdown: "absolute inset-0 cursor-pointer opacity-0",
        // La barre de nav est posée par-dessus le titre (z-10) mais laisse passer
        // les clics au centre (pointer-events-none) : sinon le bloc `month_caption`,
        // peint au-dessus, intercepterait les flèches. Seuls les deux boutons
        // redeviennent cliquables.
        nav: "pointer-events-none absolute inset-x-0 top-0 z-10 flex h-8 items-center justify-between px-0.5",
        button_previous: cn(
          buttonVariants({ variant: "outline", size: "icon" }),
          "pointer-events-auto size-7 p-0 text-muted hover:text-ink",
        ),
        button_next: cn(
          buttonVariants({ variant: "outline", size: "icon" }),
          "pointer-events-auto size-7 p-0 text-muted hover:text-ink",
        ),
        month_grid: "w-full border-collapse",
        weekdays: "flex",
        weekday: "w-9 text-[0.75rem] font-normal capitalize text-muted",
        week: "mt-1 flex w-full",
        day: "relative size-9 p-0 text-center text-sm",
        day_button: cn(
          buttonVariants({ variant: "ghost" }),
          "size-9 rounded-[var(--radius)] p-0 font-normal text-ink aria-selected:opacity-100",
        ),
        selected: "[&>button]:bg-navy [&>button]:text-white [&>button]:hover:bg-navy/90",
        today: "[&>button]:ring-1 [&>button]:ring-inset [&>button]:ring-navy/40",
        outside: "[&>button]:text-muted/40",
        disabled: "[&>button]:pointer-events-none [&>button]:opacity-40",
        range_start:
          "rounded-l-[var(--radius)] bg-navy/10 [&>button]:rounded-r-none",
        range_end: "rounded-r-[var(--radius)] bg-navy/10 [&>button]:rounded-l-none",
        range_middle:
          "bg-navy/10 [&>button]:!rounded-none [&>button]:!bg-transparent [&>button]:!text-ink [&>button]:hover:!bg-navy/15",
        hidden: "invisible",
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation, className: cls }) => {
          const Icon =
            orientation === "left"
              ? ChevronLeft
              : orientation === "right"
                ? ChevronRight
                : orientation === "up"
                  ? ChevronUp
                  : ChevronDown;
          return <Icon className={cn("size-4", cls)} />;
        },
      }}
      {...props}
    />
  );
}
