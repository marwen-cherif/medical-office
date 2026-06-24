import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { fmtEuro, MODE_OPTIONS, todayIso } from "@/lib/format";
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
      setMontant(String(depense.reste.toFixed(2)));
      setMode("especes");
      setDate(todayIso());
      setError("");
    }
  }, [depense]);

  function submit() {
    if (!depense) return;
    const v = Number(montant.replace(",", "."));
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
        <DialogHeader>
          <DialogTitle>Régler la dépense</DialogTitle>
        </DialogHeader>
        {depense && (
          <div className="space-y-3 py-2">
            <div className="flex justify-between text-sm text-muted">
              <span>Total dû</span>
              <span className="tabular-nums">{fmtEuro(depense.montant)}</span>
            </div>
            <div className="flex justify-between text-sm text-muted">
              <span>Déjà réglé</span>
              <span className="tabular-nums">{fmtEuro(depense.montant_regle)}</span>
            </div>
            <div className="flex justify-between text-sm font-semibold text-amber">
              <span>Reste à payer</span>
              <span className="tabular-nums">{fmtEuro(depense.reste)}</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="r-montant">Montant versé (€)</Label>
                <Input id="r-montant" autoFocus inputMode="decimal" value={montant}
                       onChange={(e) => setMontant(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="r-date">Date</Label>
                <Input id="r-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
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
            {error && <p className="text-xs text-red">{error}</p>}
          </div>
        )}
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={regler.isPending}>Enregistrer le versement</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
