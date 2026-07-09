import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useDepenseReglements } from "@/hooks/prestataires";
import { humanizeError } from "@/lib/errors";
import { isoToFr, modeLabel, fmtDevise } from "@/lib/format";
import type { Depense } from "@/api/types";

export function DepenseReglementsDialog({
  depense,
  onClose,
}: {
  depense: Depense | null;
  onClose: () => void;
}) {
  const q = useDepenseReglements(depense ? depense.id ?? null : null);

  return (
    <Dialog open={!!depense} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Détail des règlements</DialogTitle>
        </DialogHeader>

        {depense && (
          <div className="space-y-4 py-2">
            <div className="text-sm text-muted">
              Dépense : <span className="font-semibold text-ink">{depense.libelle || depense.motif || "Dépense"}</span> (total {fmtDevise(depense.montant)})
            </div>

            {q.isLoading && <p className="text-sm text-muted">Chargement…</p>}
            {q.isError && <p className="text-sm text-red">{humanizeError(q.error)}</p>}

            {q.data && (
              <div className="rounded-[var(--radius)] border border-line bg-white">
                {q.data.length === 0 ? (
                  <p className="p-4 text-center text-sm text-muted">Aucun versement enregistré.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {q.data.map((r) => (
                      <li key={r.id} className="flex justify-between items-center px-4 py-3 text-sm">
                        <div className="font-semibold text-green">{fmtDevise(r.montant)}</div>
                        <div className="text-right">
                          <div className="text-ink">{modeLabel(r.mode)}</div>
                          <div className="text-xs text-muted">
                            {r.date_reglement ? `le ${isoToFr(r.date_reglement)}` : "Sans date"}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="secondary" onClick={onClose}>
            Fermer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
