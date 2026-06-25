import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { humanizeError } from "@/lib/errors";
import { useCreatePrestataire, useUpdatePrestataire } from "@/hooks/prestataires";
import type { Prestataire } from "@/api/types";

export function PrestataireFormDialog({
  target,
  onClose,
  onCreated,
}: {
  target: Prestataire | "new" | null;
  onClose: () => void;
  onCreated?: (p: Prestataire) => void;
}) {
  const create = useCreatePrestataire();
  const update = useUpdatePrestataire();
  const isEdit = target && target !== "new";

  const [form, setForm] = useState({
    nom: "", prenom: "", email: "", telephone: "", adresse: "", notes: "",
  });
  const [error, setError] = useState("");
  const [confirmDup, setConfirmDup] = useState(false);

  useEffect(() => {
    if (target === "new") {
      setForm({ nom: "", prenom: "", email: "", telephone: "", adresse: "", notes: "" });
    } else if (target) {
      setForm({
        nom: target.nom, prenom: target.prenom ?? "", email: target.email ?? "",
        telephone: target.telephone ?? "", adresse: target.adresse ?? "",
        notes: target.notes ?? "",
      });
    }
    setError("");
    setConfirmDup(false);
  }, [target]);

  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  function submit() {
    if (!form.nom.trim()) return setError("Le nom / la raison sociale est obligatoire.");
    const body = {
      nom: form.nom.trim(), prenom: form.prenom.trim(),
      email: form.email.trim() || null, telephone: form.telephone.trim() || null,
      adresse: form.adresse.trim() || null, notes: form.notes.trim() || null,
      force: confirmDup,
    };
    const done = {
      onSuccess: (p: Prestataire) => {
        toast.success(isEdit ? "Prestataire mis à jour." : "Prestataire créé.");
        onCreated?.(p);
        onClose();
      },
      onError: (e: unknown) => {
        const code = (e as { error?: { code?: string } })?.error?.code;
        if (code === "DUPLICATE_PRESTATAIRE") {
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
            <DialogTitle>{isEdit ? "Modifier le prestataire" : "Nouveau prestataire"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="p-nom">Nom / Raison sociale</Label>
                <Input id="p-nom" autoFocus value={form.nom} onChange={(e) => set("nom")(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="p-prenom">Prénom</Label>
                <Input id="p-prenom" value={form.prenom} onChange={(e) => set("prenom")(e.target.value)} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="p-email">Email</Label>
                <Input id="p-email" value={form.email} onChange={(e) => set("email")(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="p-tel">Téléphone</Label>
                <Input id="p-tel" value={form.telephone} onChange={(e) => set("telephone")(e.target.value)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-adresse">Adresse</Label>
              <Textarea id="p-adresse" rows={2} value={form.adresse} onChange={(e) => set("adresse")(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="p-notes">Notes</Label>
              <Textarea id="p-notes" rows={2} value={form.notes} onChange={(e) => set("notes")(e.target.value)} />
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
