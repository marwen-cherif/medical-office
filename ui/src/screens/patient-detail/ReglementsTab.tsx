import { useState } from "react";
import { FileText, Stethoscope } from "lucide-react";
import { MoneySummary } from "@/components/common/MoneySummary";
import { Pagination } from "@/components/common/Pagination";
import { Badge } from "@/components/ui/badge";
import { humanizeError } from "@/lib/errors";
import { fmtDevise, isoToFr, modeLabel } from "@/lib/format";
import { useEncaissements } from "@/hooks/clinical";

export function ReglementsTab({ patientId }: { patientId: number }) {
  const [page, setPage] = useState(0);
  const q = useEncaissements(patientId, page);

  if (q.isLoading) return <p className="pt-4 text-sm text-muted">Chargement…</p>;
  if (q.isError) return <p className="pt-4 text-sm text-red">{humanizeError(q.error)}</p>;
  const data = q.data!;

  return (
    <div className="space-y-4 pt-4">
      <MoneySummary
        items={[
          { label: "Dû", value: data.solde.du },
          { label: "Encaissé", value: data.solde.encaisse, tone: "green" },
          { label: "Reste à recouvrer", value: data.solde.reste, tone: "amber" },
        ]}
      />

      <div className="rounded-[var(--radius)] border border-line bg-white p-4">
        <h3 className="mb-2 text-sm font-semibold text-navy">Encaissements</h3>
        {data.items.length === 0 ? (
          <p className="text-sm text-muted">Aucun encaissement.</p>
        ) : (
          data.items.map((e) => (
            <div
              key={`${e.nature}-${e.source_id}`}
              className="flex items-center gap-3 border-t border-line py-2 first:border-t-0"
            >
              <span className="w-24 text-right font-semibold tabular-nums text-green">
                {fmtDevise(e.montant)}
              </span>
              {e.nature === "acte" ? (
                <Stethoscope className="size-4 text-muted" />
              ) : (
                <FileText className="size-4 text-muted" />
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate text-ink">{e.libelle}</div>
                <div className="text-xs text-muted">
                  {modeLabel(e.mode)}
                  {e.date ? ` · ${isoToFr(e.date)}` : ""}
                </div>
              </div>
              <Badge variant="muted">{e.nature === "acte" ? "Acte" : "Note"}</Badge>
            </div>
          ))
        )}
      </div>

      <Pagination total={data.total} page={page} onPage={setPage} />
    </div>
  );
}
