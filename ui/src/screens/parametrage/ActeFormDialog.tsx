import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
import { humanizeError } from "@/lib/errors";
import { DEVISE_SYMBOLE } from "@/lib/format";
import { useCreateActe, useUpdateActe } from "@/hooks/queries";
import type { Acte } from "@/api/types";

// Validation côté UI (react-hook-form + zod). Les règles métier de fond restent
// portées par le moteur (repo.create_acte/update_acte) ; ceci ne fait qu'éviter
// un aller-retour pour les cas évidents.
const schema = z.object({
  libelle: z.string().trim().min(1, "Le libellé est obligatoire."),
  prix: z.coerce.number({ invalid_type_error: "Prix invalide." }).min(0, "Le prix doit être positif ou nul."),
  code: z.string().trim().optional(),
});
type FormValues = z.input<typeof schema>;

export function ActeFormDialog({
  target,
  onClose,
}: {
  target: Acte | "new" | null;
  onClose: () => void;
}) {
  const create = useCreateActe();
  const update = useUpdateActe();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { libelle: "", prix: 0, code: "" },
  });

  useEffect(() => {
    if (target === "new") reset({ libelle: "", prix: 0, code: "" });
    else if (target) reset({ libelle: target.libelle, prix: target.prix, code: target.code ?? "" });
  }, [target, reset]);

  function onSubmit(values: FormValues) {
    const body = {
      libelle: values.libelle.trim(),
      prix: Number(values.prix),
      code: values.code?.trim() || null,
      sort_order: target !== "new" && target ? target.sort_order : 0,
    };
    const onDone = {
      onSuccess: () => {
        toast.success("Acte enregistré.");
        onClose();
      },
      onError: (e: unknown) => toast.error(humanizeError(e)),
    };
    if (target === "new") create.mutate(body, onDone);
    else if (target) update.mutate({ id: target.id, body }, onDone);
  }

  return (
    <Dialog open={!!target} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>{target === "new" ? "Nouvel acte" : "Modifier l'acte"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label htmlFor="a-lib">Libellé</Label>
              <Input id="a-lib" autoFocus {...register("libelle")} />
              {errors.libelle && <p className="text-xs text-red">{errors.libelle.message}</p>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="a-prix">Prix ({DEVISE_SYMBOLE})</Label>
                <Input id="a-prix" inputMode="decimal" {...register("prix")} placeholder="0.00" />
                {errors.prix && <p className="text-xs text-red">{errors.prix.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="a-code">Code (optionnel)</Label>
                <Input id="a-code" {...register("code")} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={isSubmitting || create.isPending || update.isPending}>
              Enregistrer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
