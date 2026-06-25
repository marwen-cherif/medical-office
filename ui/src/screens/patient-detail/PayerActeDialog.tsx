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
import { DEVISE_SYMBOLE, fmtDevise, MODE_OPTIONS, todayIso } from "@/lib/format";
import { parseMontant, ResteApresReglement } from "@/components/common/ResteApresReglement";
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

  const saisi = parseMontant(montant);

  function submit() {
    if (!prestation) return;
    const v = parseMontant(montant);
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
              <span className="tabular-nums">{fmtDevise(prestation.montant)}</span>
            </div>
            <div className="flex justify-between text-sm text-muted">
              <span>Déjà réglé</span>
              <span className="tabular-nums">{fmtDevise(prestation.montant_regle)}</span>
            </div>
            <div className="flex justify-between text-sm text-muted">
              <span>Reste à payer</span>
              <span className="tabular-nums">{fmtDevise(prestation.reste)}</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="pa-montant">Montant ({DEVISE_SYMBOLE})</Label>
                <Input id="pa-montant" autoFocus inputMode="decimal" value={montant}
                       onChange={(e) => setMontant(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pa-date">Date</Label>
                <DatePicker id="pa-date" value={date} onChange={setDate} />
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
            <ResteApresReglement reste={prestation.reste} saisi={saisi} />
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
