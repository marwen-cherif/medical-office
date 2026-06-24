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
import { ActeCard, acteToPayload, emptyActe, type ActeValue } from "./ActeCard";

const NONE = "__none__";

export function PrestationDialog({
  patientId,
  target,
  presetPlanId,
  plans,
  defaultDenture,
  onClose,
}: {
  patientId: number;
  target: Prestation | "new" | null;
  presetPlanId?: number | null;
  plans: Plan[];
  defaultDenture?: "adulte" | "enfant";
  onClose: () => void;
}) {
  const create = useCreatePrestation(patientId);
  const update = useUpdatePrestation(patientId);
  const isEdit = target && target !== "new";

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

  function submit() {
    if (!card.libelle.trim()) return setError("Le libellé de l'acte est obligatoire.");
    const body = { ...acteToPayload(card), plan_id: planId === NONE ? null : Number(planId) };
    const done = {
      onSuccess: () => {
        toast.success("Acte enregistré.");
        onClose();
      },
      onError: (e: unknown) => setError(humanizeError(e)),
    };
    if (isEdit) update.mutate({ id: target.id, body }, done);
    else create.mutate(body, done);
  }

  return (
    <Dialog open={!!target} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
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
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={create.isPending || update.isPending}>Enregistrer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
