import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { humanizeError } from "@/lib/errors";
import { parseDents } from "@/lib/format";
import { useCreatePrestation, useUpdatePrestation } from "@/hooks/clinical";
import type { Plan, Prestation } from "@/api/types";
import { ActeCard, acteToPayload, emptyActe, validateActe, type ActeValue } from "./ActeCard";
import { SaveWithNoteButton } from "./SaveWithNoteButton";

const NONE = "__none__";

export function PrestationDialog({
  patientId,
  target,
  presetPlanId,
  plans,
  defaultDenture,
  onCreated,
  onClose,
}: {
  patientId: number;
  target: Prestation | "new" | null;
  presetPlanId?: number | null;
  plans: Plan[];
  defaultDenture?: "adulte" | "enfant";
  /** Création + enchaînement vers la note : appelé avec l'acte créé pour ouvrir la modale. */
  onCreated?: (prestationIds: number[]) => void;
  onClose: () => void;
}) {
  const create = useCreatePrestation(patientId);
  const update = useUpdatePrestation(patientId);
  const isEdit = target && target !== "new";
  const busy = create.isPending || update.isPending;

  const [card, setCard] = useState<ActeValue>(emptyActe());
  const [planId, setPlanId] = useState<string>(NONE);
  const [error, setError] = useState("");

  useEffect(() => {
    if (target === "new") {
      setCard(emptyActe());
      setPlanId(presetPlanId ? String(presetPlanId) : NONE);
    } else if (target) {
      setCard({
        libelle: target.libelle,
        montant: String(target.montant ?? ""),
        acte_id: target.acte_id ?? null,
        date_acte: target.date_acte ?? "",
        dents: parseDents(target.dents),
        note: target.note ?? "",
      });
      setPlanId(target.plan_id ? String(target.plan_id) : NONE);
    }
    setError("");
  }, [target, presetPlanId]);

  // `withNote` n'est vrai qu'en création (issue « + générer la note ») ; la validation de la
  // carte (libellé + montant) est commune aux deux issues — rien n'est créé en cas d'erreur.
  function submit(withNote = false) {
    const invalid = validateActe(card);
    if (invalid) return setError(invalid);
    const body = { ...acteToPayload(card), plan_id: planId === NONE ? null : Number(planId) };
    if (isEdit) {
      update.mutate(
        { id: target.id, body },
        {
          onSuccess: () => {
            toast.success("Acte enregistré.");
            onClose();
          },
          onError: (e: unknown) => setError(humanizeError(e)),
        },
      );
      return;
    }
    create.mutate(body, {
      onSuccess: (data) => {
        // Issue de génération : remonter l'acte créé pour ouvrir la note pré-cochée.
        // Sinon, enregistrement simple (comportement par défaut).
        if (withNote) onCreated?.([data.id]);
        else toast.success("Acte enregistré.");
        onClose();
      },
      onError: (e: unknown) => setError(humanizeError(e)),
    });
  }

  return (
    <Dialog open={!!target} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <form className="grid gap-4 [&>*]:min-w-0" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Modifier l'acte" : "Nouvel acte"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label>Plan de traitement</Label>
              <Select value={planId} onValueChange={setPlanId}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>— Aucun (acte isolé) —</SelectItem>
                  {plans.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.titre}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <ActeCard value={card} onChange={setCard} defaultDenture={defaultDenture} />
            {error && <p className="text-xs text-red">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>Annuler</Button>
            {isEdit ? (
              <Button type="submit" disabled={busy}>Enregistrer</Button>
            ) : (
              <SaveWithNoteButton disabled={busy} onGenerate={() => submit(true)} />
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
