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
import { DEVISE_SYMBOLE } from "@/lib/format";
import { useCreateDepense, usePrestataires } from "@/hooks/prestataires";

/**
 * Création d'une dépense fournisseur. Si `prestataireId` est fourni (depuis une
 * fiche prestataire) le sélecteur est masqué ; sinon il liste les prestataires.
 * « Avance » optionnelle = montant déjà réglé (montant fixe ou pourcentage).
 */
export function DepenseDialog({
  open,
  onClose,
  prestataireId,
}: {
  open: boolean;
  onClose: () => void;
  prestataireId?: number;
}) {
  const create = useCreateDepense();
  const prestataires = usePrestataires("", 0);

  const [pid, setPid] = useState<string>(prestataireId ? String(prestataireId) : "");
  const [montant, setMontant] = useState("");
  const [libelle, setLibelle] = useState("");
  const [echeance, setEcheance] = useState("");
  const [avanceType, setAvanceType] = useState<"montant" | "pourcentage">("montant");
  const [avance, setAvance] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setPid(prestataireId ? String(prestataireId) : "");
      setMontant("");
      setLibelle("");
      setEcheance("");
      setAvanceType("montant");
      setAvance("");
      setError("");
    }
  }, [open, prestataireId]);

  function submit() {
    const m = Number(montant.replace(",", "."));
    if (!pid) return setError("Sélectionnez un prestataire.");
    if (!m || m <= 0) return setError("Montant invalide.");
    let montantRegle = 0;
    const a = Number(avance.replace(",", "."));
    if (a > 0) montantRegle = avanceType === "pourcentage" ? (m * a) / 100 : a;
    create.mutate(
      {
        prestataire_id: Number(pid),
        montant: m,
        montant_regle: Math.min(montantRegle, m),
        libelle: libelle.trim() || null,
        date_echeance: echeance || null,
      },
      {
        onSuccess: () => {
          toast.success("Dépense ajoutée.");
          onClose();
        },
        onError: (e) => setError(humanizeError(e)),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle dépense</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {!prestataireId && (
            <div className="space-y-2">
              <Label>Prestataire</Label>
              <Select value={pid} onValueChange={setPid}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionner…" />
                </SelectTrigger>
                <SelectContent>
                  {(prestataires.data?.items ?? []).map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.display}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="d-montant">Montant ({DEVISE_SYMBOLE})</Label>
              <Input id="d-montant" autoFocus inputMode="decimal" value={montant}
                     onChange={(e) => setMontant(e.target.value)} placeholder="0.00" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="d-echeance">Échéance</Label>
              <DatePicker id="d-echeance" value={echeance} onChange={setEcheance} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="d-libelle">Libellé (optionnel)</Label>
            <Input id="d-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Avance</Label>
              <Select value={avanceType} onValueChange={(v) => setAvanceType(v as "montant" | "pourcentage")}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="montant">Montant ({DEVISE_SYMBOLE})</SelectItem>
                  <SelectItem value="pourcentage">Pourcentage (%)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="d-avance">Versée à la création</Label>
              <Input id="d-avance" inputMode="decimal" value={avance}
                     onChange={(e) => setAvance(e.target.value)} placeholder="0" />
            </div>
          </div>
          {error && <p className="text-xs text-red">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={create.isPending}>Ajouter la dépense</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
