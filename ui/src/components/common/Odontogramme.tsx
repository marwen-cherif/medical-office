import { useState } from "react";
import { DENTS_PERMANENTES, DENTS_TEMPORAIRES } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Odontogramme interactif (notation FDI). Sélection multiple de dents par clic,
 * bascule Adulte (permanentes) / Enfant (temporaires). `value` = liste de numéros
 * FDI ; `onChange` reçoit la nouvelle liste à chaque clic.
 */
export function Odontogramme({
  value,
  onChange,
  defaultDenture = "adulte",
}: {
  value: string[];
  onChange: (dents: string[]) => void;
  defaultDenture?: "adulte" | "enfant";
}) {
  const [denture, setDenture] = useState<"adulte" | "enfant">(defaultDenture);
  const map = denture === "adulte" ? DENTS_PERMANENTES : DENTS_TEMPORAIRES;
  const selected = new Set(value);

  function toggle(num: string) {
    const next = new Set(selected);
    if (next.has(num)) next.delete(num);
    else next.add(num);
    onChange([...next]);
  }

  const upper = denture === "adulte" ? [map[1], map[2]] : [map[5], map[6]];
  const lower = denture === "adulte" ? [map[4], map[3]] : [map[8], map[7]];

  const Tooth = ({ num }: { num: string }) => (
    <button
      type="button"
      onClick={() => toggle(num)}
      className={cn(
        "h-7 w-7 rounded border text-[11px] font-medium tabular-nums transition-colors",
        selected.has(num)
          ? "border-navy bg-navy text-white"
          : "border-line bg-white text-ink hover:bg-bg",
      )}
    >
      {num}
    </button>
  );

  const Row = ({ quadrants }: { quadrants: string[][] }) => (
    <div className="flex justify-center gap-3">
      {quadrants.map((q, i) => (
        <div key={i} className="flex gap-1">
          {q.map((num) => (
            <Tooth key={num} num={num} />
          ))}
        </div>
      ))}
    </div>
  );

  return (
    <div className="space-y-2 rounded-[var(--radius)] border border-line bg-bg/50 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted">Odontogramme</span>
        <div className="flex overflow-hidden rounded-[var(--radius)] border border-line text-xs">
          {(["adulte", "enfant"] as const).map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDenture(d)}
              className={cn(
                "px-2.5 py-1 capitalize transition-colors",
                denture === d ? "bg-navy text-white" : "bg-white text-ink hover:bg-bg",
              )}
            >
              {d}
            </button>
          ))}
        </div>
      </div>
      <div className="space-y-1.5 overflow-x-auto py-1">
        <Row quadrants={upper} />
        <div className="mx-auto h-px w-3/4 bg-line" />
        <Row quadrants={lower} />
      </div>
      {value.length > 0 && (
        <div className="text-xs text-muted">
          Sélection : <span className="font-medium text-ink">{value.join(", ")}</span>
        </div>
      )}
    </div>
  );
}
