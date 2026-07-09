import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { DatePicker } from "@/components/common/DatePicker";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { humanizeError } from "@/lib/errors";
import { useCreatePatient, useUpdatePatient } from "@/hooks/patients";
import type { Patient } from "@/api/types";

export function PatientFormDialog({
  target,
  onClose,
  onCreated,
}: {
  target: Patient | "new" | null;
  onClose: () => void;
  onCreated?: (p: Patient) => void;
}) {
  const create = useCreatePatient();
  const update = useUpdatePatient();
  const isEdit = target && target !== "new";

  const [form, setForm] = useState({
    nom: "", prenom: "", date_naissance: "", email: "", telephone: "", adresse: "", notes: "",
  });
  const [error, setError] = useState("");
  const [confirmDup, setConfirmDup] = useState(false);

  useEffect(() => {
    if (target === "new") {
      setForm({ nom: "", prenom: "", date_naissance: "", email: "", telephone: "", adresse: "", notes: "" });
    } else if (target) {
      setForm({
        nom: target.nom, prenom: target.prenom, date_naissance: target.date_naissance ?? "",
        email: target.email ?? "", telephone: target.telephone ?? "",
        adresse: target.adresse ?? "", notes: target.notes ?? "",
      });
    }
    setError("");
    setConfirmDup(false);
  }, [target]);

  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  function submit() {
    if (!form.nom.trim() || !form.prenom.trim())
      return setError("Le nom et le prénom sont obligatoires.");
    const body = {
      nom: form.nom.trim(), prenom: form.prenom.trim(),
      date_naissance: form.date_naissance || null, email: form.email.trim() || null,
      telephone: form.telephone.trim() || null, adresse: form.adresse.trim() || null,
      notes: form.notes.trim() || null, force: confirmDup,
    };
    const done = {
      onSuccess: (p: Patient) => {
        toast.success(isEdit ? "Patient mis à jour." : "Patient créé.");
        onCreated?.(p);
        onClose();
      },
      onError: (e: unknown) => {
        const code = (e as { error?: { code?: string } })?.error?.code;
        if (code === "DUPLICATE_PATIENT") {
          setConfirmDup(true);
          setError(humanizeError(e) + " Cliquez à nouveau pour créer quand même.");
        } else {
          setError(humanizeError(e));
        }
      },
    };
    if (isEdit) update.mutate({ id: target.id, body }, done);
    else create.mutate(body, done);
  }

  return (
    <Dialog open={!!target} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Modifier le patient" : "Nouveau patient"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="pt-nom">Nom</Label>
                <Input id="pt-nom" autoFocus value={form.nom} onChange={(e) => set("nom")(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pt-prenom">Prénom</Label>
                <Input id="pt-prenom" value={form.prenom} onChange={(e) => set("prenom")(e.target.value)} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="pt-ddn">Date de naissance</Label>
                <DatePicker id="pt-ddn" dropdown value={form.date_naissance}
                            onChange={set("date_naissance")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pt-tel">Téléphone</Label>
                <Input id="pt-tel" value={form.telephone} onChange={(e) => set("telephone")(e.target.value)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pt-email">Email</Label>
              <Input id="pt-email" value={form.email} onChange={(e) => set("email")(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pt-adresse">Adresse</Label>
              <Textarea id="pt-adresse" rows={2} value={form.adresse} onChange={(e) => set("adresse")(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pt-notes">Notes</Label>
              <Textarea id="pt-notes" rows={2} value={form.notes} onChange={(e) => set("notes")(e.target.value)} />
            </div>
            {error && <p className="text-xs text-red">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={create.isPending || update.isPending}>Enregistrer</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
