import { useMemo, useState } from "react";
import { toast } from "sonner";
import { ExternalLink, FilePlus2, Layers, Pencil, Settings2, Tag, Trash2 } from "lucide-react";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { humanizeError } from "@/lib/errors";
import { CategoryField } from "@/components/common/CategoryField";
import {
  useCategories,
  useCreateTemplate,
  useDeleteTemplate,
  useOpenInWord,
  useRenameTemplate,
  useSetTemplateCategory,
  useTemplates,
} from "@/hooks/queries";
import type { Template } from "@/api/types";
import { VariablesDialog } from "./VariablesDialog";

export function ModelesTab() {
  const templates = useTemplates();
  const categories = useCategories();
  const createTpl = useCreateTemplate();
  const renameTpl = useRenameTemplate();
  const deleteTpl = useDeleteTemplate();
  const openWord = useOpenInWord();
  const setCategory = useSetTemplateCategory();

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [renameTarget, setRenameTarget] = useState<Template | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [categoryTarget, setCategoryTarget] = useState<Template | null>(null);
  const [categoryValue, setCategoryValue] = useState("");
  const [varsTarget, setVarsTarget] = useState<Template | null>(null);

  const grouped = useMemo(() => {
    const map = new Map<string, Template[]>();
    for (const t of templates.data ?? []) {
      const key = t.categorie ?? "Sans catégorie";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(t);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], "fr"));
  }, [templates.data]);

  const catColor = (nom: string) =>
    categories.data?.find((c) => c.nom === nom)?.couleur ?? undefined;

  async function onCreate() {
    const name = newName.trim();
    if (!name) return;
    try {
      const tpl = await createTpl.mutateAsync(name);
      const cat = newCategory.trim();
      // Catégorie (facultative) portée par le modèle, créée paresseusement au besoin.
      if (cat) await setCategory.mutateAsync({ name: tpl.name, categorie: cat });
      toast.success("Modèle créé.");
      setCreateOpen(false);
      setNewName("");
      setNewCategory("");
    } catch (e) {
      toast.error(humanizeError(e));
    }
  }

  function onRename() {
    if (!renameTarget) return;
    renameTpl.mutate(
      { name: renameTarget.name, newName: renameValue.trim() },
      {
        onSuccess: () => {
          toast.success("Modèle renommé.");
          setRenameTarget(null);
        },
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  function onSaveCategory() {
    if (!categoryTarget) return;
    const value = categoryValue.trim();
    setCategory.mutate(
      { name: categoryTarget.name, categorie: value || null },
      {
        onSuccess: () => {
          toast.success("Catégorie mise à jour.");
          setCategoryTarget(null);
        },
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  function onDelete(t: Template) {
    if (!confirm(`Supprimer le modèle « ${t.label} » ? Le fichier .docx sera supprimé.`)) return;
    deleteTpl.mutate(t.name, {
      onSuccess: () => toast.success("Modèle supprimé."),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  function onOpenWord(t: Template) {
    openWord.mutate(t.name, {
      onSuccess: () => toast.message("Ouverture dans Word…"),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">
          {templates.data?.length ?? 0} modèle(s). Un modèle contenant des balises{" "}
          <code className="rounded bg-bg px-1">&lt;L_*&gt;</code> est une note multi-lignes.
        </p>
        <Button
          onClick={() => {
            setNewName("");
            setNewCategory("");
            setCreateOpen(true);
          }}
        >
          <FilePlus2 className="size-4" /> Nouveau modèle
        </Button>
      </div>

      {templates.isLoading && <p className="text-sm text-muted">Chargement…</p>}
      {templates.isError && (
        <p className="text-sm text-red">{humanizeError(templates.error)}</p>
      )}

      {grouped.map(([cat, items]) => (
        <div key={cat} className="rounded-[var(--radius)] border border-line bg-white">
          <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
            <span
              className="size-2.5 rounded-full"
              style={{ background: catColor(cat) ?? "#94a3b8" }}
            />
            <span className="text-sm font-semibold text-ink">{cat}</span>
            <Badge variant="muted">{items.length}</Badge>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Modèle</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((t) => (
                <TableRow key={t.name}>
                  <TableCell className="font-medium">{t.label}</TableCell>
                  <TableCell>
                    {t.is_multiligne ? (
                      <Badge variant="default">
                        <Layers className="mr-1 size-3" /> Multi-lignes
                      </Badge>
                    ) : (
                      <Badge variant="muted">Simple</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" title="Ouvrir dans Word"
                        onClick={() => onOpenWord(t)}>
                        <ExternalLink className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Configurer les variables"
                        onClick={() => setVarsTarget(t)}>
                        <Settings2 className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Catégorie"
                        onClick={() => {
                          setCategoryTarget(t);
                          setCategoryValue(t.categorie ?? "");
                        }}>
                        <Tag className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Renommer"
                        onClick={() => {
                          setRenameTarget(t);
                          setRenameValue(t.name);
                        }}>
                        <Pencil className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" title="Supprimer"
                        onClick={() => onDelete(t)}>
                        <Trash2 className="size-4 text-red" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ))}

      {/* Création */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); onCreate(); }}>
            <DialogHeader>
              <DialogTitle>Nouveau modèle</DialogTitle>
              <DialogDescription>
                Un fichier .docx vide avec quelques balises est créé. Modifiez-le ensuite dans Word.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="tpl-name">Nom du modèle</Label>
              <Input id="tpl-name" value={newName} onChange={(e) => setNewName(e.target.value)}
                placeholder="ex. note_honoraires" autoFocus />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tpl-new-cat">Catégorie (facultatif)</Label>
              <CategoryField id="tpl-new-cat" value={newCategory} onChange={setNewCategory} />
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>Annuler</Button>
              <Button type="submit" disabled={createTpl.isPending || setCategory.isPending}>Créer</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Renommer */}
      <Dialog open={!!renameTarget} onOpenChange={(o) => !o && setRenameTarget(null)}>
        <DialogContent>
          <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); onRename(); }}>
            <DialogHeader>
              <DialogTitle>Renommer le modèle</DialogTitle>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="tpl-rename">Nouveau nom</Label>
              <Input id="tpl-rename" value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)} autoFocus />
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setRenameTarget(null)}>Annuler</Button>
              <Button type="submit" disabled={renameTpl.isPending}>Renommer</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Catégorie */}
      <Dialog open={!!categoryTarget} onOpenChange={(o) => !o && setCategoryTarget(null)}>
        <DialogContent>
          <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); onSaveCategory(); }}>
            <DialogHeader>
              <DialogTitle>Catégorie du modèle</DialogTitle>
              <DialogDescription>
                Texte libre. Laisser vide pour retirer la catégorie.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="tpl-cat">Catégorie</Label>
              <CategoryField id="tpl-cat" value={categoryValue} onChange={setCategoryValue} />
            </div>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setCategoryTarget(null)}>Annuler</Button>
              <Button type="submit" disabled={setCategory.isPending}>Enregistrer</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Variables */}
      {varsTarget && (
        <VariablesDialog
          template={varsTarget}
          open={!!varsTarget}
          onClose={() => setVarsTarget(null)}
        />
      )}
    </div>
  );
}
