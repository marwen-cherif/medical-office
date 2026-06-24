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
import { usePrestationReglement } from "@/hooks/clinical";
import type { Prestation } from "@/api/types";

/** Règlement (partiel ou total) d'un acte précis. */
export function PayerActeDialog({
  patientId,
  prestation,
  onClose,
}: {
  patientId: number;
  prestation: Prestation | null;
  onClose: () => void;
}) {
  const regler = usePrestationReglement(patientId);
  const [montant, setMontant] = useState("");
  const [mode, setMode] = useState("especes");
  const [date, setDate] = useState(todayIso());
  const [error, setError] = useState("");

  useEffect(() => {
    if (prestation) {
      setMontant(prestation.reste.toFixed(2));
      setMode("especes");
      setDate(todayIso());
      setError("");
    }
  }, [prestation]);

  function submit() {
    if (!prestation) return;
    const v = Number(montant.replace(",", "."));
    if (!v || v <= 0) return setError("Montant invalide.");
    if (v > prestation.reste + 1e-6) return setError("Le montant dépasse le reste à payer.");
    regler.mutate(
      { id: prestation.id, body: { montant: v, mode, date_reglement: date } },
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
    <Dialog open={!!prestation} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Régler l'acte</DialogTitle>
        </DialogHeader>
        {prestation && (
          <div className="space-y-3 py-2">
            <p className="text-sm font-medium text-ink">{prestation.libelle}</p>
            <div className="flex justify-between text-sm text-muted">
              <span>Total dû</span>
              <span className="tabular-nums">{fmtEuro(prestation.montant)}</span>
            </div>
            <div className="flex justify-between text-sm text-muted">
              <span>Déjà réglé</span>
              <span className="tabular-nums">{fmtEuro(prestation.montant_regle)}</span>
            </div>
            <div className="flex justify-between text-sm font-semibold text-amber">
              <span>Reste à payer</span>
              <span className="tabular-nums">{fmtEuro(prestation.reste)}</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="pa-montant">Montant (€)</Label>
                <Input id="pa-montant" autoFocus inputMode="decimal" value={montant}
                       onChange={(e) => setMontant(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pa-date">Date</Label>
                <Input id="pa-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
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
          <Button onClick={submit} disabled={regler.isPending}>Enregistrer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
