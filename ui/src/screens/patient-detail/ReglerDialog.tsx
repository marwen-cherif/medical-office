import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Stethoscope, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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
import { DEVISE_SYMBOLE, fmtDevise, isoToFr, MODE_OPTIONS, todayIso } from "@/lib/format";
import { useCascadeRegler, useCreances } from "@/hooks/clinical";

/**
 * Règlement global « en cascade » : un montant réparti des créances les plus
 * anciennes aux plus récentes. Aperçu d'allocation en direct (calque Flet).
 */
export function ReglerDialog({
  patientId,
  open,
  onClose,
}: {
  patientId: number;
  open: boolean;
  onClose: () => void;
}) {
  const [includeNotes, setIncludeNotes] = useState(false);
  const creances = useCreances(open ? patientId : null, includeNotes);
  const cascade = useCascadeRegler(patientId);

  const totalReste = useMemo(
    () => (creances.data ?? []).reduce((s, c) => s + c.reste, 0),
    [creances.data],
  );

  const [montant, setMontant] = useState("");
  const [mode, setMode] = useState("especes");
  const [date, setDate] = useState(todayIso());
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setMode("especes");
      setDate(todayIso());
      setError("");
    }
  }, [open]);

  useEffect(() => {
    if (open && creances.data) setMontant(totalReste.toFixed(2));
  }, [open, totalReste, creances.data]);

  // Aperçu d'allocation du plus ancien au plus récent.
  const preview = useMemo(() => {
    let budget = Number(montant.replace(",", ".")) || 0;
    return (creances.data ?? []).map((c) => {
      const alloue = Math.min(budget, c.reste);
      budget -= alloue;
      return { c, alloue };
    });
  }, [montant, creances.data]);

  const saisi = Number(montant.replace(",", ".")) || 0;
  const restant = Math.max(0, saisi - totalReste);

  function submit() {
    const v = Number(montant.replace(",", "."));
    if (!v || v <= 0) return setError("Montant invalide.");
    cascade.mutate(
      { montant: v, mode, date_reglement: date, include_notes: includeNotes },
      {
        onSuccess: (res) => {
          toast.success(`Règlement réparti : ${fmtDevise(res.alloue)}.`);
          onClose();
        },
        onError: (e) => setError(humanizeError(e)),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Régler (cascade)</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="rg-montant">Montant ({DEVISE_SYMBOLE})</Label>
              <Input id="rg-montant" autoFocus inputMode="decimal" value={montant}
                     onChange={(e) => setMontant(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rg-date">Date</Label>
              <DatePicker id="rg-date" value={date} onChange={setDate} />
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
          <label className="flex items-center gap-2 text-sm text-ink">
            <Switch checked={includeNotes} onCheckedChange={setIncludeNotes} />
            Inclure les notes (paiements) en attente
          </label>

          <div className="rounded-[var(--radius)] border border-line bg-bg/50 p-3">
            <div className="mb-2 text-xs font-medium text-muted">Répartition</div>
            {creances.isLoading && <p className="text-sm text-muted">Chargement…</p>}
            {!creances.isLoading && preview.length === 0 && (
              <p className="text-sm text-muted">Aucune créance à régler.</p>
            )}
            <div className="space-y-1.5">
              {preview.map(({ c, alloue }) => (
                <div key={`${c.nature}-${c.source_id}`} className="flex items-center gap-2 text-sm">
                  {c.nature === "acte" ? (
                    <Stethoscope className="size-4 text-muted" />
                  ) : (
                    <FileText className="size-4 text-muted" />
                  )}
                  <span className="flex-1 truncate text-ink">
                    {c.libelle}
                    {c.date ? <span className="text-muted"> · {isoToFr(c.date)}</span> : null}
                  </span>
                  <span className="tabular-nums text-muted">{fmtDevise(c.reste)}</span>
                  <span className="w-24 text-right tabular-nums font-medium text-green">
                    {alloue > 0 ? `+ ${fmtDevise(alloue)}` : "—"}
                  </span>
                </div>
              ))}
            </div>
            {restant > 0 && (
              <p className="mt-2 text-xs text-amber">
                Surplus non alloué : {fmtDevise(restant)} (le montant dépasse le total dû).
              </p>
            )}
          </div>
          {error && <p className="text-xs text-red">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={cascade.isPending}>Confirmer le règlement</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
