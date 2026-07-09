import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { humanizeError } from "@/lib/errors";
import { useCreatePlan, useCreatePrestation, useUpdatePlan } from "@/hooks/clinical";
import type { Plan } from "@/api/types";
import { ActeCard, acteToPayload, emptyActe, validateActe, type ActeValue } from "./ActeCard";
import { SaveWithNoteButton } from "./SaveWithNoteButton";

export function PlanDialog({
  patientId,
  target,
  defaultDenture,
  onCreated,
  onClose,
}: {
  patientId: number;
  target: Plan | "new" | null;
  defaultDenture?: "adulte" | "enfant";
  /** Création + enchaînement vers la note : appelé avec les actes du plan créés. */
  onCreated?: (prestationIds: number[]) => void;
  onClose: () => void;
}) {
  const createPlan = useCreatePlan(patientId);
  const updatePlan = useUpdatePlan(patientId);
  const createPrestation = useCreatePrestation(patientId);
  const isEdit = target && target !== "new";

  const [titre, setTitre] = useState("");
  const [notes, setNotes] = useState("");
  const [cards, setCards] = useState<ActeValue[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (target === "new") {
      setTitre("");
      setNotes("");
      // Démarre avec une carte d'acte vide (cas courant : on saisit au moins un acte).
      setCards([emptyActe()]);
    } else if (target) {
      setTitre(target.titre);
      setNotes(target.notes ?? "");
      setCards([]);
    }
    setError("");
  }, [target]);

  // `withNote` n'est vrai qu'en création. Les cartes sans libellé sont ignorées (validation
  // commune aux deux issues). Si aucun acte n'est créé, on se rabat sur l'enregistrement
  // simple (pas de note vide) en informant via le toast « Plan créé. ».
  async function submit(withNote = false) {
    if (!titre.trim()) return setError("Le titre du plan est obligatoire.");
    // Validation des cartes avant toute création (commune aux deux issues) : les cartes
    // entièrement vides sont ignorées, une carte amorcée mais invalide bloque tout.
    if (!isEdit) {
      for (const c of cards) {
        const vide = !c.libelle.trim() && !c.montant.trim() && !c.dents.length && !c.note.trim();
        if (vide) continue;
        const invalid = validateActe(c);
        if (invalid) return setError(invalid);
      }
    }
    setBusy(true);
    try {
      if (isEdit) {
        await updatePlan.mutateAsync({ planId: target.id, body: { titre: titre.trim(), notes: notes.trim() || null } });
        toast.success("Plan mis à jour.");
        onClose();
        return;
      }
      const plan = await createPlan.mutateAsync({ titre: titre.trim(), notes: notes.trim() || null });
      const createdIds: number[] = [];
      for (const c of cards) {
        if (!c.libelle.trim()) continue;
        const pres = await createPrestation.mutateAsync({ ...acteToPayload(c), plan_id: plan.id });
        createdIds.push(pres.id);
      }
      if (withNote && createdIds.length > 0) onCreated?.(createdIds);
      else toast.success("Plan créé.");
      onClose();
    } catch (e) {
      setError(humanizeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={!!target} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <form className="grid gap-4 [&>*]:min-w-0" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Modifier le plan" : "Nouveau plan de traitement"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label htmlFor="pl-titre">Titre</Label>
              <Input id="pl-titre" autoFocus value={titre} onChange={(e) => setTitre(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pl-notes">Notes (optionnel)</Label>
              <Textarea id="pl-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
            {!isEdit && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Actes du plan</Label>
                  <Button type="button" variant="secondary" size="sm" onClick={() => setCards((c) => [...c, emptyActe()])}>
                    <Plus className="size-4" /> Ajouter un acte
                  </Button>
                </div>
                {cards.length === 0 && (
                  <p className="text-xs text-muted">Aucun acte. Vous pourrez aussi en ajouter après création.</p>
                )}
                {cards.map((c, i) => (
                  <ActeCard
                    key={i}
                    value={c}
                    defaultDenture={defaultDenture}
                    onChange={(v) => setCards((arr) => arr.map((x, j) => (j === i ? v : x)))}
                    onRemove={() => setCards((arr) => arr.filter((_, j) => j !== i))}
                  />
                ))}
              </div>
            )}
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
