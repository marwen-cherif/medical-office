import { useState } from "react";
import { toast } from "sonner";
import { Banknote, Pencil, Plus, Trash2, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { humanizeError } from "@/lib/errors";
import { fmtDevise, isoToFr, parseDents } from "@/lib/format";
import {
  useClinical,
  useDeletePaiement,
  useDeletePlan,
  useDeletePrestation,
} from "@/hooks/clinical";
import type { Paiement, Plan, Prestation } from "@/api/types";
import { OdontogrammeClinique } from "@/components/common/OdontogrammeClinique";
import { PlanDialog } from "./PlanDialog";
import { PrestationDialog } from "./PrestationDialog";
import { PayerActeDialog } from "./PayerActeDialog";
import { PayerNoteDialog } from "./PayerNoteDialog";
import { ReglerDialog } from "./ReglerDialog";

function DentsBadges({ dents }: { dents: string | null | undefined }) {
  const list = parseDents(dents);
  if (!list.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {list.map((d) => (
        <span key={d} className="rounded bg-teal/20 px-1.5 py-0.5 text-[11px] font-medium text-teal-dark">
          {d}
        </span>
      ))}
    </div>
  );
}

function PrestationRow({
  pres,
  onRegler,
  onEdit,
  onDelete,
  onHover,
}: {
  pres: Prestation;
  onRegler: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onHover?: (dents: string[] | null) => void;
}) {
  const pct = pres.montant > 0 ? Math.min(100, (pres.montant_regle / pres.montant) * 100) : 0;
  return (
    <div
      className="flex items-start gap-3 border-t border-line py-2 first:border-t-0 hover:bg-bg/60"
      onMouseEnter={() => onHover?.(parseDents(pres.dents))}
      onMouseLeave={() => onHover?.(null)}
    >
      <div className="w-28 shrink-0 text-right">
        <div className="font-semibold tabular-nums text-ink">{fmtDevise(pres.montant)}</div>
        {pres.facturable && (
          <div className="text-xs text-muted">
            réglé {fmtDevise(pres.montant_regle)} · reste {fmtDevise(pres.reste)}
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-ink">{pres.libelle}</span>
          <DentsBadges dents={pres.dents} />
        </div>
        {pres.facturable && (
          <div className="mt-1 h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-line">
            <div className="h-full bg-green" style={{ width: `${pct}%` }} />
          </div>
        )}
        <div className="mt-1 text-xs text-muted">
          {pres.date_acte ? isoToFr(pres.date_acte) : "Sans date"}
          {pres.note ? ` · ${pres.note}` : ""}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {!pres.facturable ? (
          <Badge variant="muted">Contrôle</Badge>
        ) : pres.reste <= 0 ? (
          <Badge variant="success">Réglé</Badge>
        ) : pres.montant_regle > 0 ? (
          <Badge variant="outline">Partiel</Badge>
        ) : (
          <Badge>À régler</Badge>
        )}
        {pres.facturable && pres.reste > 0 && (
          <Button variant="ghost" size="icon" title="Régler cet acte" onClick={onRegler}>
            <Banknote className="size-4 text-green" />
          </Button>
        )}
        <Button variant="ghost" size="icon" title="Modifier" onClick={onEdit}>
          <Pencil className="size-4" />
        </Button>
        <Button variant="ghost" size="icon" title="Supprimer" onClick={onDelete}>
          <Trash2 className="size-4 text-red" />
        </Button>
      </div>
    </div>
  );
}

export function PlansActesTab({
  patientId,
  denture,
}: {
  patientId: number;
  denture: "adulte" | "enfant";
}) {
  const clinical = useClinical(patientId);
  const delPrestation = useDeletePrestation(patientId);
  const delPlan = useDeletePlan(patientId);
  const delPaiement = useDeletePaiement(patientId);

  const [planDialog, setPlanDialog] = useState<Plan | "new" | null>(null);
  const [presDialog, setPresDialog] = useState<{ target: Prestation | "new"; planId?: number | null } | null>(null);
  const [payActe, setPayActe] = useState<Prestation | null>(null);
  const [payNote, setPayNote] = useState<Paiement | null>(null);
  const [cascade, setCascade] = useState(false);
  const [hoverFdis, setHoverFdis] = useState<string[] | null>(null);

  if (clinical.isLoading) return <p className="pt-4 text-sm text-muted">Chargement…</p>;
  if (clinical.isError) return <p className="pt-4 text-sm text-red">{humanizeError(clinical.error)}</p>;
  const data = clinical.data!;
  const plans = data.plans.map((g) => g.plan);

  function removePrestation(pres: Prestation) {
    if (!confirm(`Supprimer l'acte « ${pres.libelle} » ?`)) return;
    delPrestation.mutate(pres.id, {
      onSuccess: () => toast.success("Acte supprimé."),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  function removePlan(plan: Plan) {
    if (!confirm(`Supprimer le plan « ${plan.titre} » ? Ses actes deviennent isolés.`)) return;
    delPlan.mutate(plan.id, {
      onSuccess: () => toast.success("Plan supprimé."),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  return (
    <div className="space-y-5 pt-4">
      {/* En-tête + schéma dentaire : collés en haut pendant le défilement de la liste */}
      <div className="sticky top-0 z-20 -mt-4 space-y-4 bg-bg pt-4 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="flex-1 text-lg font-semibold text-ink">Plans &amp; actes</h2>
          {data.total_a_regler > 0 && (
            <Button onClick={() => setCascade(true)}>
              <Wallet className="size-4" /> Régler ({fmtDevise(data.total_a_regler)})
            </Button>
          )}
          <Button variant="secondary" onClick={() => setPlanDialog("new")}>
            <Plus className="size-4" /> Plan
          </Button>
          <Button variant="secondary" onClick={() => setPresDialog({ target: "new" })}>
            <Plus className="size-4" /> Acte
          </Button>
        </div>

        {/* Schéma dentaire (lecture seule) */}
        <OdontogrammeClinique clinical={data} denture={denture} highlightFdis={hoverFdis ?? []} />
      </div>

      {/* Notes en attente */}
      {data.notes_en_attente.length > 0 && (
        <section className="space-y-2 rounded-[var(--radius)] border border-line bg-white p-4">
          <h3 className="text-sm font-semibold text-navy">Notes en attente</h3>
          {data.notes_en_attente.map((n) => {
            const partiel = n.montant_regle > 1e-6;
            return (
              <div key={n.id} className="flex items-center gap-3 border-t border-line py-2 first:border-t-0">
                <span className="w-24 text-right font-semibold tabular-nums text-amber">{fmtDevise(n.reste)}</span>
                <div className="flex-1 text-sm">
                  <div className="text-ink">{n.notes || "Note"}</div>
                  <div className="text-xs text-muted">
                    {partiel && <span>Réglé {fmtDevise(n.montant_regle)} / {fmtDevise(n.montant)} · </span>}
                    {n.date_echeance ? `Échéance : ${isoToFr(n.date_echeance)}` : "Sans échéance"}
                  </div>
                </div>
                <Button variant="ghost" size="icon" title="Régler" onClick={() => setPayNote(n)}>
                  <Banknote className="size-4 text-green" />
                </Button>
                {!partiel && (
                  <Button variant="ghost" size="icon" title="Annuler"
                          onClick={() => delPaiement.mutate(n.id, {
                            onSuccess: () => toast.success("Note annulée."),
                            onError: (e) => toast.error(humanizeError(e)),
                          })}>
                    <Trash2 className="size-4 text-red" />
                  </Button>
                )}
              </div>
            );
          })}
        </section>
      )}

      {/* Actes isolés */}
      <section className="space-y-1 rounded-[var(--radius)] border border-line bg-white p-4">
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-navy">Actes isolés</h3>
          <Button variant="ghost" size="sm" onClick={() => setPresDialog({ target: "new", planId: null })}>
            <Plus className="size-4" /> Ajouter
          </Button>
        </div>
        {data.isoles.length === 0 ? (
          <p className="text-sm text-muted">Aucun acte isolé.</p>
        ) : (
          data.isoles.map((pres) => (
            <PrestationRow
              key={pres.id}
              pres={pres}
              onRegler={() => setPayActe(pres)}
              onEdit={() => setPresDialog({ target: pres })}
              onDelete={() => removePrestation(pres)}
              onHover={setHoverFdis}
            />
          ))
        )}
      </section>

      {/* Plans */}
      {data.plans.map((g) => {
        const t = g.totaux;
        const pct = t.du > 0 ? Math.min(100, (t.encaisse / t.du) * 100) : 0;
        return (
          <section key={g.plan.id} className="space-y-1 rounded-[var(--radius)] border border-line bg-white p-4">
            <div className="flex items-center gap-2">
              <h3 className="flex-1 font-semibold text-ink">{g.plan.titre}</h3>
              <span className="text-xs text-muted">
                dû {fmtDevise(t.du)} · encaissé {fmtDevise(t.encaisse)} · reste {fmtDevise(t.reste)}
              </span>
              <Button variant="ghost" size="icon" title="Ajouter un acte"
                      onClick={() => setPresDialog({ target: "new", planId: g.plan.id })}>
                <Plus className="size-4" />
              </Button>
              <Button variant="ghost" size="icon" title="Modifier le plan" onClick={() => setPlanDialog(g.plan)}>
                <Pencil className="size-4" />
              </Button>
              <Button variant="ghost" size="icon" title="Supprimer le plan" onClick={() => removePlan(g.plan)}>
                <Trash2 className="size-4 text-red" />
              </Button>
            </div>
            <div className="mb-1 h-1.5 w-full overflow-hidden rounded-full bg-line">
              <div className="h-full bg-green" style={{ width: `${pct}%` }} />
            </div>
            {g.prestations.length === 0 ? (
              <p className="text-sm text-muted">Aucun acte dans ce plan.</p>
            ) : (
              g.prestations.map((pres) => (
                <PrestationRow
                  key={pres.id}
                  pres={pres}
                  onRegler={() => setPayActe(pres)}
                  onEdit={() => setPresDialog({ target: pres })}
                  onDelete={() => removePrestation(pres)}
                />
              ))
            )}
          </section>
        );
      })}

      <PlanDialog patientId={patientId} target={planDialog} defaultDenture={denture}
                  onClose={() => setPlanDialog(null)} />
      <PrestationDialog
        patientId={patientId}
        target={presDialog?.target ?? null}
        presetPlanId={presDialog?.planId}
        plans={plans}
        defaultDenture={denture}
        onClose={() => setPresDialog(null)}
      />
      <PayerActeDialog patientId={patientId} prestation={payActe} onClose={() => setPayActe(null)} />
      <PayerNoteDialog patientId={patientId} paiement={payNote} onClose={() => setPayNote(null)} />
      <ReglerDialog patientId={patientId} open={cascade} onClose={() => setCascade(false)} />
    </div>
  );
}
