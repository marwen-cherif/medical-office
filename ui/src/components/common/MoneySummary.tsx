import { Wallet } from "lucide-react";
import { fmtEuro } from "@/lib/format";
import { cn } from "@/lib/utils";

export type MoneyItem = { label: string; value: number; tone?: "ink" | "green" | "amber" | "red" };

const TONE: Record<NonNullable<MoneyItem["tone"]>, string> = {
  ink: "text-ink",
  green: "text-green",
  amber: "text-amber",
  red: "text-red",
};

/**
 * Carte récapitulative à plusieurs cellules monétaires (calque `_money_summary`).
 *
 * `layout="row"` (défaut) : cellules côte à côte, séparées verticalement — adapté à un
 * conteneur large (Finances, fiche prestataire, onglet Règlements).
 * `layout="column"` : cellules empilées — pour un conteneur étroit (sidebar de la fiche
 * patient), où la version en ligne ne laisse pas assez de place et tronque les montants.
 */
export function MoneySummary({ items, layout = "row" }: { items: MoneyItem[]; layout?: "row" | "column" }) {
  const column = layout === "column";
  return (
    <div
      className={cn(
        "flex gap-4 rounded-[var(--radius)] border border-line bg-white p-4",
        column ? "items-start" : "items-center",
      )}
    >
      <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-navy/10 text-navy">
        <Wallet className="size-5" />
      </div>
      <div className={cn("min-w-0 flex-1", column ? "flex flex-col divide-y divide-line" : "flex divide-x divide-line")}>
        {items.map((it, i) => (
          <div key={i} className={cn("min-w-0", column ? "py-2 first:pt-0 last:pb-0" : "flex-1 px-4 first:pl-0")}>
            <div className="text-xs text-muted">{it.label}</div>
            <div className={cn("text-lg font-semibold tabular-nums", TONE[it.tone ?? "ink"])}>
              {fmtEuro(it.value)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
