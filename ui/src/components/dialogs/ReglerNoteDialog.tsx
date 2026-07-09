import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DatePicker } from "@/components/common/DatePicker";
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
import { DEVISE_SYMBOLE, MODE_OPTIONS, montantInput, todayIso } from "@/lib/format";
import { MontantRow } from "@/components/common/Montant";
import { parseMontant, ResteApresReglement } from "@/components/common/ResteApresReglement";
import { useReglerNote } from "@/hooks/finances";

/** Cible minimale (issue d'une ligne de créance Finances). */
export type NoteCible = { id: number; libelle: string; montant: number; reste: number };

/** Versement (partiel ou total) sur une note depuis l'écran Finances. */
export function ReglerNoteDialog({
  note,
  onClose,
}: {
  note: NoteCible | null;
  onClose: () => void;
}) {
  const regler = useReglerNote();
  const [montant, setMontant] = useState("");
  const [mode, setMode] = useState("especes");
  const [date, setDate] = useState(todayIso());
  const [error, setError] = useState("");

  useEffect(() => {
    if (note) {
      setMontant(montantInput(note.reste));
      setMode("especes");
      setDate(todayIso());
      setError("");
    }
  }, [note]);

  const saisi = parseMontant(montant);

  function submit() {
    if (!note) return;
    const v = parseMontant(montant);
    if (!v || v <= 0) return setError("Montant invalide.");
    if (v > (note.reste ?? 0) + 1e-6) return setError("Le montant dépasse le reste à recouvrer.");
    regler.mutate(
      { id: note.id, body: { montant: v, mode, date_reglement: date } },
      {
        onSuccess: () => {
          toast.success("Règlement enregistré.");
          onClose();
        },
        onError: (e) => setError(humanizeError(e)),
      },
    );
  }

  const dejaRegle = note ? note.montant - note.reste : 0;

  return (
    <Dialog open={!!note} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <DialogHeader>
            <DialogTitle>Régler la note</DialogTitle>
          </DialogHeader>
          {note && (
            <div className="space-y-3 py-2">
              <p className="text-sm font-medium text-ink">{note.libelle}</p>
              <MontantRow label="Total dû" value={note.montant} />
              <MontantRow label="Déjà réglé" value={dejaRegle} />
              <MontantRow label="Reste à recouvrer" value={note.reste} />
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="rn-montant">Montant ({DEVISE_SYMBOLE})</Label>
                  <Input id="rn-montant" autoFocus inputMode="decimal" value={montant}
                         onChange={(e) => setMontant(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rn-date">Date</Label>
                  <DatePicker id="rn-date" value={date} onChange={setDate} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Mode de règlement</Label>
                <Select value={mode} onValueChange={setMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MODE_OPTIONS.map((m) => (
                      <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <ResteApresReglement reste={note.reste ?? 0} saisi={saisi} />
              {error && <p className="text-xs text-red">{error}</p>}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={regler.isPending}>Enregistrer</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
