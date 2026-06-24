import { useMemo, useState } from "react";
import { humanizeError } from "@/lib/errors";
import { humanize, isoToFrDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useAudit } from "@/hooks/clinical";
import type { AuditEntry } from "@/api/types";

// Catégorisation des actions pour les filtres (calque _AUDIT_FILTERS de Flet).
const FILTERS: { key: string; label: string; match: (a: string) => boolean }[] = [
  { key: "tous", label: "Tous", match: () => true },
  { key: "fiche", label: "Fiche", match: (a) => a.startsWith("fiche") },
  { key: "plans", label: "Plans", match: (a) => a.startsWith("plan") },
  { key: "actes", label: "Actes", match: (a) => a.startsWith("acte") },
  { key: "paiements", label: "Paiements", match: (a) => a.startsWith("paiement") || a.includes("regle") },
  { key: "documents", label: "Documents", match: (a) => a.includes("document") || a.includes("note") || a.includes("brouillon") },
];

function describe(detail: unknown): string {
  if (detail == null) return "";
  if (typeof detail === "string") return detail;
  if (typeof detail === "object") {
    const o = detail as Record<string, unknown>;
    if (o.champs && typeof o.champs === "object") {
      const champs = o.champs as Record<string, unknown>;
      return Object.keys(champs)
        .map((k) => humanize(k))
        .join(", ");
    }
    const parts: string[] = [];
    for (const [k, v] of Object.entries(o)) {
      if (v == null || typeof v === "object") continue;
      parts.push(`${humanize(k)} : ${v}`);
      if (parts.length >= 3) break;
    }
    return parts.join(" · ");
  }
  return String(detail);
}

function dayLabel(ts: string): string {
  const d = new Date(ts.replace(" ", "T"));
  if (isNaN(d.getTime())) return ts.slice(0, 10);
  const today = new Date();
  const yest = new Date();
  yest.setDate(today.getDate() - 1);
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  if (same(d, today)) return "Aujourd'hui";
  if (same(d, yest)) return "Hier";
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" });
}

export function HistoriqueTab({ patientId }: { patientId: number }) {
  const q = useAudit(patientId);
  const [filter, setFilter] = useState("tous");

  const grouped = useMemo(() => {
    const f = FILTERS.find((x) => x.key === filter) ?? FILTERS[0];
    const rows = (q.data ?? []).filter((r: AuditEntry) => f.match(r.action));
    const map = new Map<string, AuditEntry[]>();
    for (const r of rows) {
      const day = dayLabel(r.ts);
      if (!map.has(day)) map.set(day, []);
      map.get(day)!.push(r);
    }
    return [...map.entries()];
  }, [q.data, filter]);

  if (q.isLoading) return <p className="pt-4 text-sm text-muted">Chargement…</p>;
  if (q.isError) return <p className="pt-4 text-sm text-red">{humanizeError(q.error)}</p>;

  return (
    <div className="space-y-4 pt-4">
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
              filter === f.key
                ? "border-navy bg-navy text-white"
                : "border-line bg-white text-ink hover:bg-bg",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {grouped.length === 0 && (
        <div className="rounded-[var(--radius)] border border-line bg-white py-10 text-center text-muted">
          Aucun événement.
        </div>
      )}

      {grouped.map(([day, rows]) => (
        <section key={day} className="rounded-[var(--radius)] border border-line bg-white p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{day}</h3>
          <div className="space-y-2">
            {rows.map((r, i) => {
              const desc = describe(r.detail);
              return (
                <div key={i} className="flex gap-3 border-t border-line py-2 text-sm first:border-t-0">
                  <span className="w-12 shrink-0 text-xs text-muted">
                    {isoToFrDateTime(r.ts).slice(-5)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-ink">{humanize(r.action)}</div>
                    {desc && <div className="text-xs text-muted">{desc}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
