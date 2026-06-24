import { useState } from "react";
import { toast } from "sonner";
import { Mail, Pencil, Plus, Star, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { humanizeError } from "@/lib/errors";
import {
  useCreateMailTemplate,
  useDeleteMailTemplate,
  useMailTemplates,
  useSetDefaultMailTemplate,
  useUpdateMailTemplate,
} from "@/hooks/queries";
import type { MailTemplate } from "@/api/types";

export function EmailsTab() {
  const list = useMailTemplates();
  const create = useCreateMailTemplate();
  const update = useUpdateMailTemplate();
  const del = useDeleteMailTemplate();
  const setDefault = useSetDefaultMailTemplate();

  const [editTarget, setEditTarget] = useState<MailTemplate | "new" | null>(null);
  const [name, setName] = useState("");
  const [mailjetId, setMailjetId] = useState("");

  function openEditor(t: MailTemplate | "new") {
    setEditTarget(t);
    setName(t === "new" ? "" : t.name);
    setMailjetId(t === "new" ? "" : String(t.mailjet_template_id));
  }

  function onSave() {
    const body = {
      name: name.trim(),
      mailjet_template_id: Number(mailjetId),
      is_default: editTarget !== "new" ? (editTarget?.is_default ?? false) : false,
    };
    if (!body.name || Number.isNaN(body.mailjet_template_id)) {
      toast.error("Nom et identifiant Mailjet requis.");
      return;
    }
    const onDone = {
      onSuccess: () => {
        toast.success("Modèle d'email enregistré.");
        setEditTarget(null);
      },
      onError: (e: unknown) => toast.error(humanizeError(e)),
    };
    if (editTarget === "new") create.mutate(body, onDone);
    else if (editTarget) update.mutate({ id: editTarget.id, body }, onDone);
  }

  function onDelete(t: MailTemplate) {
    if (!confirm(`Supprimer le modèle d'email « ${t.name} » ?`)) return;
    del.mutate(t.id, {
      onSuccess: () => toast.success("Supprimé."),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">
          Modèles transactionnels Mailjet utilisés pour le corps des emails.
        </p>
        <Button onClick={() => openEditor("new")}>
          <Plus className="size-4" /> Nouveau modèle
        </Button>
      </div>

      {list.isLoading && <p className="text-sm text-muted">Chargement…</p>}
      {list.isError && <p className="text-sm text-red">{humanizeError(list.error)}</p>}

      <div className="rounded-[var(--radius)] border border-line bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nom</TableHead>
              <TableHead>ID Mailjet</TableHead>
              <TableHead>Par défaut</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(list.data ?? []).map((t) => (
              <TableRow key={t.id}>
                <TableCell className="font-medium">
                  <span className="inline-flex items-center gap-2">
                    <Mail className="size-4 text-muted" /> {t.name}
                  </span>
                </TableCell>
                <TableCell className="font-mono text-muted">{t.mailjet_template_id}</TableCell>
                <TableCell>
                  {t.is_default ? (
                    <Badge variant="success">Par défaut</Badge>
                  ) : (
                    <Button variant="ghost" size="sm" onClick={() => setDefault.mutate(t.id)}>
                      <Star className="size-4" /> Définir
                    </Button>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="icon" title="Modifier" onClick={() => openEditor(t)}>
                      <Pencil className="size-4" />
                    </Button>
                    <Button variant="ghost" size="icon" title="Supprimer" onClick={() => onDelete(t)}>
                      <Trash2 className="size-4 text-red" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {list.data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="py-6 text-center text-muted">
                  Aucun modèle d'email.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={!!editTarget} onOpenChange={(o) => !o && setEditTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editTarget === "new" ? "Nouveau modèle d'email" : "Modifier le modèle d'email"}
            </DialogTitle>
            <DialogDescription>
              L'identifiant correspond au template transactionnel défini dans Mailjet.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="mt-name">Nom</Label>
              <Input id="mt-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mt-id">ID template Mailjet</Label>
              <Input id="mt-id" inputMode="numeric" value={mailjetId}
                onChange={(e) => setMailjetId(e.target.value)} placeholder="ex. 1234567" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setEditTarget(null)}>Annuler</Button>
            <Button onClick={onSave} disabled={create.isPending || update.isPending}>
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
