import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { humanizeError } from "@/lib/errors";
import { useSetTemplateFields, useTemplateFields, useTemplatePlaceholders } from "@/hooks/queries";
import type { Field, Template } from "@/api/types";

const TYPES = [
  { value: "text", label: "Texte" },
  { value: "paragraph", label: "Paragraphe" },
  { value: "number", label: "Nombre" },
  { value: "date", label: "Date" },
];

export function VariablesDialog({
  template,
  open,
  onClose,
}: {
  template: Template;
  open: boolean;
  onClose: () => void;
}) {
  const placeholders = useTemplatePlaceholders(template.name);
  const fields = useTemplateFields(template.name);
  const save = useSetTemplateFields();
  const [rows, setRows] = useState<Record<string, Field>>({});

  // Fusionne les balises personnalisées du .docx avec la config enregistrée.
  useEffect(() => {
    if (!placeholders.data || !fields.data) return;
    const existing = new Map(fields.data.map((f) => [f.tag, f]));
    const next: Record<string, Field> = {};
    for (const tag of placeholders.data.custom_tags) {
      next[tag] =
        existing.get(tag) ?? { tag, label: tag, type: "text", default_value: "" };
    }
    setRows(next);
  }, [placeholders.data, fields.data]);

  function update(tag: string, patch: Partial<Field>) {
    setRows((r) => ({ ...r, [tag]: { ...r[tag], ...patch } }));
  }

  function onSave() {
    save.mutate(
      { name: template.name, fields: Object.values(rows) },
      {
        onSuccess: () => {
          toast.success("Variables enregistrées.");
          onClose();
        },
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  const customTags = placeholders.data?.custom_tags ?? [];
  const autoTags = placeholders.data?.auto_tags ?? [];

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); onSave(); }}>
          <DialogHeader>
            <DialogTitle>Variables — {template.label}</DialogTitle>
            <DialogDescription>
              Les balises patient sont remplies automatiquement. Configurez le libellé, le type et
              la valeur par défaut des balises personnalisées.
            </DialogDescription>
          </DialogHeader>

          {placeholders.isLoading && <p className="text-sm text-muted">Chargement…</p>}
          {placeholders.isError && (
            <p className="text-sm text-red">{humanizeError(placeholders.error)}</p>
          )}

          {autoTags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <span className="text-xs text-muted">Auto :</span>
              {autoTags.map((t) => (
                <Badge key={t} variant="muted">{t}</Badge>
              ))}
            </div>
          )}

          <div className="max-h-[50vh] space-y-3 overflow-auto">
            {customTags.length === 0 && !placeholders.isLoading && (
              <p className="text-sm text-muted">Aucune balise personnalisée à configurer.</p>
            )}
            {customTags.map((tag) => {
              const row = rows[tag];
              if (!row) return null;
              return (
                <div key={tag} className="grid grid-cols-[auto_1fr_8rem_1fr] items-center gap-2">
                  <Badge variant="outline" className="font-mono">{tag}</Badge>
                  <Input
                    placeholder="Libellé"
                    value={row.label}
                    onChange={(e) => update(tag, { label: e.target.value })}
                  />
                  <Select value={row.type} onValueChange={(v) => update(tag, { type: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {TYPES.map((t) => (
                        <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder="Valeur par défaut"
                    value={row.default_value}
                    onChange={(e) => update(tag, { default_value: e.target.value })}
                  />
                </div>
              );
            })}
          </div>

          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={save.isPending || customTags.length === 0}>
              Enregistrer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
