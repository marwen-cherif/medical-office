import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DatePicker } from "@/components/common/DatePicker";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
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
import { usePaiementReglement } from "@/hooks/clinical";
import type { Paiement } from "@/api/types";

/** Règlement (partiel ou total) d'une note précise — calque de PayerActeDialog. */
export function PayerNoteDialog({
  patientId,
  paiement,
  onClose,
}: {
  patientId: number;
  paiement: Paiement | null;
  onClose: () => void;
}) {
  const regler = usePaiementReglement(patientId);
  const [montant, setMontant] = useState("");
  const [mode, setMode] = useState("especes");
  const [date, setDate] = useState(todayIso());
  const [error, setError] = useState("");

  useEffect(() => {
    if (paiement) {
      setMontant(montantInput(paiement.reste));
      setMode("especes");
      setDate(todayIso());
      setError("");
    }
  }, [paiement]);

  const saisi = parseMontant(montant);

  function submit() {
    if (!paiement) return;
    const v = parseMontant(montant);
    if (!v || v <= 0) return setError("Montant invalide.");
    if (v > (paiement.reste ?? 0) + 1e-6) return setError("Le montant dépasse le reste à recouvrer.");
    regler.mutate(
      { id: paiement.id, body: { montant: v, mode, date_reglement: date } },
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
    <Sheet open={!!paiement} onOpenChange={(o) => !o && onClose()}>
      <SheetContent>
        <form className="flex h-full flex-col" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <SheetHeader>
            <SheetTitle>Régler la note</SheetTitle>
          </SheetHeader>
          {paiement && (
            <SheetBody className="space-y-3">
              <p className="text-sm font-medium text-ink">{paiement.notes || "Note d'honoraires"}</p>
              <MontantRow label="Total dû" value={paiement.montant} />
              <MontantRow label="Déjà réglé" value={paiement.montant_regle} />
              <MontantRow label="Reste à recouvrer" value={paiement.reste} />
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="pn-montant">Montant ({DEVISE_SYMBOLE})</Label>
                  <Input id="pn-montant" autoFocus inputMode="decimal" value={montant}
                         onChange={(e) => setMontant(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="pn-date">Date</Label>
                  <DatePicker id="pn-date" value={date} onChange={setDate} />
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
              <ResteApresReglement reste={paiement.reste ?? 0} saisi={saisi} />
              {error && <p className="text-xs text-red">{error}</p>}
            </SheetBody>
          )}
          <SheetFooter>
            <Button type="button" variant="secondary" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={regler.isPending}>Enregistrer</Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
