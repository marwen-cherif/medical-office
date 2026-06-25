import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Odontogramme } from "@/components/common/Odontogramme";
import { DatePicker } from "@/components/common/DatePicker";
import { useActes } from "@/hooks/queries";
import { DEVISE_SYMBOLE, fmtDevise } from "@/lib/format";

/** Valeur saisie d'un acte (carte). Montant en chaîne pour la saisie. */
export type ActeValue = {
  libelle: string;
  montant: string;
  acte_id: number | null;
  date_acte: string;
  dents: string[];
  note: string;
};

export function emptyActe(): ActeValue {
  return { libelle: "", montant: "", acte_id: null, date_acte: "", dents: [], note: "" };
}

/** Carte de saisie d'un acte : référentiel (pré-remplissage) + odontogramme. */
export function ActeCard({
  value,
  onChange,
  onRemove,
  defaultDenture = "adulte",
}: {
  value: ActeValue;
  onChange: (v: ActeValue) => void;
  onRemove?: () => void;
  defaultDenture?: "adulte" | "enfant";
}) {
  const actes = useActes("", false);
  const set = (patch: Partial<ActeValue>) => onChange({ ...value, ...patch });

  function pickRef(id: string) {
    const a = actes.data?.items.find((x) => String(x.id) === id);
    if (a) set({ acte_id: a.id, libelle: a.libelle, montant: String(a.prix) });
  }

  return (
    <div className="space-y-3 rounded-[var(--radius)] border border-line bg-white p-3">
      <div className="flex items-start gap-2">
        <div className="flex-1 space-y-3">
          <div className="space-y-2">
            <Label>Acte du référentiel (optionnel)</Label>
            <Select value={value.acte_id ? String(value.acte_id) : ""} onValueChange={pickRef}>
              <SelectTrigger>
                <SelectValue placeholder="Choisir un acte tarifé…" />
              </SelectTrigger>
              <SelectContent>
                {(actes.data?.items ?? []).map((a) => (
                  <SelectItem key={a.id} value={String(a.id)}>
                    {a.libelle} — {fmtDevise(a.prix)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-[1fr_8rem_9rem] gap-2">
            <div className="space-y-2">
              <Label>Libellé</Label>
              <Input value={value.libelle} onChange={(e) => set({ libelle: e.target.value, acte_id: null })} />
            </div>
            <div className="space-y-2">
              <Label>Montant ({DEVISE_SYMBOLE})</Label>
              <Input inputMode="decimal" value={value.montant} placeholder="0.00"
                     onChange={(e) => set({ montant: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Date</Label>
              <DatePicker value={value.date_acte} onChange={(date_acte) => set({ date_acte })} />
            </div>
          </div>
        </div>
        {onRemove && (
          <Button variant="ghost" size="icon" title="Retirer" onClick={onRemove} className="mt-6 text-red">
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>
      <Odontogramme value={value.dents} onChange={(dents) => set({ dents })} defaultDenture={defaultDenture} />
      <div className="space-y-2">
        <Label>Note (optionnel)</Label>
        <Textarea rows={2} value={value.note} onChange={(e) => set({ note: e.target.value })} />
      </div>
    </div>
  );
}

/** Transforme une carte en payload d'API (montant numérique, dents jointes). */
export function acteToPayload(v: ActeValue) {
  return {
    libelle: v.libelle.trim(),
    montant: Number((v.montant || "0").replace(",", ".")) || 0,
    acte_id: v.acte_id,
    date_acte: v.date_acte || null,
    dents: v.dents.length ? v.dents.join(", ") : null,
    note: v.note.trim() || null,
  };
}
