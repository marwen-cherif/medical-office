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
import { useRegleDepense } from "@/hooks/prestataires";
import type { Depense } from "@/api/types";

/** Versement (partiel ou total) sur une dépense fournisseur. */
export function ReglerDepenseDialog({
  depense,
  prestataireId,
  onClose,
}: {
  depense: Depense | null;
  prestataireId?: number;
  onClose: () => void;
}) {
  const regler = useRegleDepense(prestataireId);
  const [montant, setMontant] = useState("");
  const [mode, setMode] = useState("especes");
  const [date, setDate] = useState(todayIso());
  const [error, setError] = useState("");

  useEffect(() => {
    if (depense) {
      setMontant(montantInput(depense.reste));
      setMode("especes");
      setDate(todayIso());
      setError("");
    }
  }, [depense]);

  const saisi = parseMontant(montant);

  function submit() {
    if (!depense) return;
    const v = parseMontant(montant);
    if (!v || v <= 0) return setError("Montant invalide.");
    if (v > depense.reste + 1e-6) return setError("Le versement dépasse le reste dû.");
    regler.mutate(
      { id: depense.id, body: { versement: v, mode, date_reglement: date } },
      {
        onSuccess: () => {
          toast.success("Règlement enregistré.");
          onClose();
        },
        onError: (e) => setError(humanizeError(e)),
      },
    );
  }

  return (
    <Dialog open={!!depense} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <DialogHeader>
            <DialogTitle>Régler la dépense</DialogTitle>
          </DialogHeader>
          {depense && (
            <div className="space-y-3 py-2">
              <MontantRow label="Total dû" value={depense.montant} />
              <MontantRow label="Déjà réglé" value={depense.montant_regle} />
              <MontantRow label="Reste à payer" value={depense.reste} />
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="r-montant">Montant versé ({DEVISE_SYMBOLE})</Label>
                  <Input id="r-montant" autoFocus inputMode="decimal" value={montant}
                         onChange={(e) => setMontant(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="r-date">Date</Label>
                  <DatePicker id="r-date" value={date} onChange={setDate} />
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
              <ResteApresReglement reste={depense.reste} saisi={saisi} label="Reste à payer après versement" />
              {error && <p className="text-xs text-red">{error}</p>}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={regler.isPending}>Enregistrer le versement</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
