import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Sparkles, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
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
import { DEVISE_SYMBOLE, montantInput } from "@/lib/format";
import {
  useCreateDepense,
  useExtractFactureMontant,
  useFactureIaDisponible,
  useImportFacture,
} from "@/hooks/prestataires";

type IaTone = "muted" | "green" | "amber";

/**
 * Import d'une facture fournisseur (réplique l'oracle Flet `_import_facture_dialog`).
 *
 * À l'ouverture, si l'extraction IA est configurée, le montant TTC est **lu sur le
 * scan par IA puis pré-rempli** dans un champ **éditable** (jamais auto-validé) ; le
 * bouton « Relire (IA) » relance la lecture. À la validation : archivage de la facture
 * (avec le montant édité) **+** création optionnelle d'une dépense liée (avance =
 * montant déjà réglé, en valeur ou en pourcentage).
 *
 * Monté en permanence ; `file != null` ouvre le dialogue et porte le fichier choisi.
 */
export function ImportFactureDialog({
  file,
  prestataireId,
  onClose,
}: {
  file: File | null;
  prestataireId: number;
  onClose: () => void;
}) {
  const iaQ = useFactureIaDisponible();
  const disponible = iaQ.data?.disponible ?? false;
  const extract = useExtractFactureMontant();
  const importFacture = useImportFacture(prestataireId);
  const createDepense = useCreateDepense();

  const [montant, setMontant] = useState("");
  const [ia, setIa] = useState<{ text: string; tone: IaTone }>({ text: "", tone: "muted" });
  const [echeance, setEcheance] = useState("");
  const [addDep, setAddDep] = useState(true);
  const [avanceType, setAvanceType] = useState<"montant" | "pourcentage">("montant");
  const [avance, setAvance] = useState("");
  const [motif, setMotif] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Garde-fou : ne lancer l'IA (ou afficher « non configurée ») qu'une fois par fichier.
  const handledFile = useRef<File | null>(null);

  function runIa(f: File) {
    setIa({ text: "Lecture de la facture par IA…", tone: "muted" });
    extract.mutate(f, {
      onSuccess: (res) => {
        if (res.montant != null) {
          setMontant(montantInput(res.montant));
          setIa({ text: "Montant lu par IA — vérifiez avant d'importer.", tone: "green" });
        } else {
          setIa({ text: "IA : montant non trouvé, saisissez-le manuellement.", tone: "amber" });
        }
      },
      onError: () =>
        setIa({ text: "IA : échec de lecture, saisissez le montant manuellement.", tone: "amber" }),
    });
  }

  // Réinitialise le formulaire à chaque nouveau fichier.
  useEffect(() => {
    if (!file) {
      handledFile.current = null;
      return;
    }
    setMontant("");
    setEcheance("");
    setAddDep(true);
    setAvanceType("montant");
    setAvance("");
    setMotif("");
    setError("");
    setIa({ text: "", tone: "muted" });
  }, [file]);

  // Auto-extraction à l'ouverture (une fois la disponibilité IA connue).
  useEffect(() => {
    if (!file || iaQ.isLoading) return;
    if (handledFile.current === file) return;
    handledFile.current = file;
    if (disponible) {
      runIa(file);
    } else {
      setIa({ text: "Extraction IA non configurée — saisie manuelle du montant.", tone: "muted" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file, disponible, iaQ.isLoading]);

  async function submit() {
    setError("");
    const m = parseNum(montant);
    if (addDep && (m == null || m <= 0)) {
      setError("Renseignez un montant total (> 0) pour créer la dépense.");
      return;
    }
    if (!file) return;
    setSaving(true);
    try {
      const fac = await importFacture.mutateAsync({ file, montant: m });
      if (addDep && m != null && m > 0) {
        let paye = 0;
        const a = parseNum(avance);
        if (a != null && a > 0) {
          paye = avanceType === "pourcentage" ? (m * a) / 100 : a;
          paye = Math.max(0, Math.min(paye, m));
        }
        await createDepense.mutateAsync({
          prestataire_id: prestataireId,
          montant: m,
          montant_regle: paye,
          motif: motif.trim() || null,
          date_echeance: echeance || null,
          facture_id: fac.id,
        });
      }
      toast.success("Facture importée.");
      onClose();
    } catch (e) {
      setError(humanizeError(e));
    } finally {
      setSaving(false);
    }
  }

  const iaColor =
    ia.tone === "green" ? "text-green" : ia.tone === "amber" ? "text-amber" : "text-muted";

  return (
    <Dialog open={!!file} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <DialogHeader>
            <DialogTitle>Importer une facture</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {file && (
              <p className="truncate text-xs text-muted">Fichier : {file.name}</p>
            )}
            <div className="space-y-2">
              <Label htmlFor="if-montant">Montant total TTC ({DEVISE_SYMBOLE})</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="if-montant"
                  autoFocus
                  inputMode="decimal"
                  value={montant}
                  onChange={(e) => setMontant(e.target.value)}
                  placeholder="0.00"
                />
                {disponible && (
                  <Button
                    type="button"
                    variant="secondary"
                    className="shrink-0"
                    disabled={!file || extract.isPending}
                    onClick={() => file && runIa(file)}
                  >
                    <Sparkles className="size-4" /> Relire (IA)
                  </Button>
                )}
              </div>
              {ia.text && <p className={`text-xs ${iaColor}`}>{ia.text}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="if-echeance">Échéance (optionnelle)</Label>
              <DatePicker id="if-echeance" value={echeance} onChange={setEcheance} />
            </div>
            <div className="border-t border-line pt-3">
              <label className="flex items-center gap-2 text-sm text-ink">
                <Checkbox
                  checked={addDep}
                  onCheckedChange={(c) => setAddDep(c)}
                />
                Ajouter une ligne de dépense
              </label>
            </div>
            {addDep && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label>Avance</Label>
                    <Select
                      value={avanceType}
                      onValueChange={(v) => setAvanceType(v as "montant" | "pourcentage")}
                    >
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
                    <Label htmlFor="if-avance">Part déjà payée</Label>
                    <Input
                      id="if-avance"
                      inputMode="decimal"
                      value={avance}
                      onChange={(e) => setAvance(e.target.value)}
                      placeholder="0"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="if-motif">Motif (optionnel)</Label>
                  <Input
                    id="if-motif"
                    value={motif}
                    onChange={(e) => setMotif(e.target.value)}
                    placeholder="ex. Avance"
                  />
                </div>
              </>
            )}
            {error && <p className="text-xs text-red">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={saving}>
              <Upload className="size-4" /> Importer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Parse une saisie montant (virgule ou point) → nombre, ou undefined si vide/invalide. */
function parseNum(s: string): number | undefined {
  if (!s || !s.trim()) return undefined;
  const v = Number(s.replace(",", "."));
  return Number.isFinite(v) ? v : undefined;
}
