import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import { ExternalLink, FilePlus2, Layers, Pencil, Settings2, Tag, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { humanizeError } from '@/lib/errors';
import { CategoryField } from '@/components/common/CategoryField';
import { CategoriesImportExport } from './CategoriesImportExport';
import {
  useCategories,
  useCreateTemplate,
  useDeleteTemplate,
  useOpenInWord,
  useRenameTemplate,
  useSetTemplateCategory,
  useTemplates,
  useUpdateCategory,
  useWhatsAppSettings,
} from '@/hooks/queries';
import type { Category, Template } from '@/api/types';
import { VariablesDialog } from './VariablesDialog';

export function ModelesTab() {
  const templates = useTemplates();
  const categories = useCategories();
  const createTpl = useCreateTemplate();
  const renameTpl = useRenameTemplate();
  const deleteTpl = useDeleteTemplate();
  const openWord = useOpenInWord();
  const setCategory = useSetTemplateCategory();

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCategory, setNewCategory] = useState('');
  const [renameTarget, setRenameTarget] = useState<Template | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [categoryTarget, setCategoryTarget] = useState<Template | null>(null);
  const [categoryValue, setCategoryValue] = useState('');
  const [varsTarget, setVarsTarget] = useState<Template | null>(null);

  const [editCategoryTarget, setEditCategoryTarget] = useState<Category | null>(null);
  const [editCategoryColor, setEditCategoryColor] = useState('');
  const [editCategoryIcon, setEditCategoryIcon] = useState('');
  const [editCategoryOrder, setEditCategoryOrder] = useState<number>(0);
  const [editCategoryWhatsApp, setEditCategoryWhatsApp] = useState('');

  const updateCategory = useUpdateCategory();
  const waSettings = useWhatsAppSettings();

  const fallbackMessage = waSettings.data?.fallback_message || "Bonjour <PRENOM> <NOM>, voici votre <DOCUMENT>.";

  const grouped = useMemo(() => {
    const map = new Map<string, Template[]>();
    for (const t of templates.data ?? []) {
      const key = t.categorie ?? 'Sans catégorie';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(t);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], 'fr'));
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
      toast.success('Modèle créé.');
      setCreateOpen(false);
      setNewName('');
      setNewCategory('');
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
          toast.success('Modèle renommé.');
          setRenameTarget(null);
        },
        onError: (e) => toast.error(humanizeError(e)),
      }
    );
  }

  function onSaveCategory() {
    if (!categoryTarget) return;
    const value = categoryValue.trim();
    setCategory.mutate(
      { name: categoryTarget.name, categorie: value || null },
      {
        onSuccess: () => {
          toast.success('Catégorie mise à jour.');
          setCategoryTarget(null);
        },
        onError: (e) => toast.error(humanizeError(e)),
      }
    );
  }

  async function onSaveCategoryDetails() {
    if (!editCategoryTarget) return;
    try {
      await updateCategory.mutateAsync({
        nom: editCategoryTarget.nom,
        body: {
          couleur: editCategoryColor.trim() || null,
          icone: editCategoryIcon.trim() || null,
          sort_order: editCategoryOrder,
          whatsapp_message: editCategoryWhatsApp.trim() || null,
        },
      });
      toast.success('Catégorie mise à jour.');
      setEditCategoryTarget(null);
    } catch (e) {
      toast.error(humanizeError(e));
    }
  }

  function onDelete(t: Template) {
    if (!confirm(`Supprimer le modèle « ${t.label} » ? Le fichier .docx sera supprimé.`)) return;
    deleteTpl.mutate(t.name, {
      onSuccess: () => toast.success('Modèle supprimé.'),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  function onOpenWord(t: Template) {
    openWord.mutate(t.name, {
      onSuccess: () => toast.message('Ouverture dans Word…'),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">
          {templates.data?.length ?? 0} modèle(s). Un modèle contenant des balises{' '}
          <code className="rounded bg-bg px-1">&lt;L_*&gt;</code> est une note multi-lignes. Les
          notes disposent aussi de <code className="rounded bg-bg px-1">&lt;DENTS&gt;</code>/
          <code className="rounded bg-bg px-1">&lt;NB_DENTS&gt;</code> (dents concernées) et de{' '}
          <code className="rounded bg-bg px-1">&lt;ODONTOGRAMME&gt;</code> (schéma dentaire — à
          placer dans un paragraphe dédié).
        </p>
        <div className="flex gap-2">
          <CategoriesImportExport />
          <Button
            onClick={() => {
              setNewName('');
              setNewCategory('');
              setCreateOpen(true);
            }}
          >
            <FilePlus2 className="size-4" /> Nouveau modèle
          </Button>
        </div>
      </div>

      {templates.isLoading && <p className="text-sm text-muted">Chargement…</p>}
      {templates.isError && <p className="text-sm text-red">{humanizeError(templates.error)}</p>}

      {grouped.map(([cat, items]) => (
        <div key={cat} className="rounded-[var(--radius)] border border-line bg-white">
          <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
            <span
              className="size-2.5 rounded-full"
              style={{ background: catColor(cat) ?? '#94a3b8' }}
            />
            <span className="text-sm font-semibold text-ink">{cat}</span>
            <Badge variant="muted">{items.length}</Badge>
            {cat !== 'Sans catégorie' && (
              <Button
                variant="ghost"
                size="icon"
                className="size-6 ml-1 text-muted hover:text-ink"
                title="Modifier la catégorie"
                onClick={() => {
                  const fullCat = categories.data?.find((c) => c.nom === cat);
                  if (fullCat) {
                    setEditCategoryTarget(fullCat);
                    setEditCategoryColor(fullCat.couleur ?? '');
                    setEditCategoryIcon(fullCat.icone ?? '');
                    setEditCategoryOrder(fullCat.sort_order ?? 0);
                    setEditCategoryWhatsApp(fullCat.whatsapp_message ?? '');
                  } else {
                    // Fallback de sécurité
                    setEditCategoryTarget({ nom: cat, couleur: '', icone: '', sort_order: 0, whatsapp_message: '' });
                    setEditCategoryColor('');
                    setEditCategoryIcon('');
                    setEditCategoryOrder(0);
                    setEditCategoryWhatsApp('');
                  }
                }}
              >
                <Pencil className="size-3" />
              </Button>
            )}
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
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Ouvrir dans Word"
                        onClick={() => onOpenWord(t)}
                      >
                        <ExternalLink className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Configurer les variables"
                        onClick={() => setVarsTarget(t)}
                      >
                        <Settings2 className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Catégorie"
                        onClick={() => {
                          setCategoryTarget(t);
                          setCategoryValue(t.categorie ?? '');
                        }}
                      >
                        <Tag className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Renommer"
                        onClick={() => {
                          setRenameTarget(t);
                          setRenameValue(t.name);
                        }}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        title="Supprimer"
                        onClick={() => onDelete(t)}
                      >
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
      <Sheet open={createOpen} onOpenChange={setCreateOpen}>
        <SheetContent>
          <form
            className="flex h-full flex-col"
            onSubmit={(e) => {
              e.preventDefault();
              onCreate();
            }}
          >
            <SheetHeader>
              <SheetTitle>Nouveau modèle</SheetTitle>
              <SheetDescription>
                Un fichier .docx vide avec quelques balises est créé. Modifiez-le ensuite dans Word.
              </SheetDescription>
            </SheetHeader>
            <SheetBody className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="tpl-name">Nom du modèle</Label>
                <Input
                  id="tpl-name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="ex. note_honoraires"
                  autoFocus
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tpl-new-cat">Catégorie (facultatif)</Label>
                <CategoryField id="tpl-new-cat" value={newCategory} onChange={setNewCategory} />
              </div>
            </SheetBody>
            <SheetFooter>
              <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>
                Annuler
              </Button>
              <Button type="submit" disabled={createTpl.isPending || setCategory.isPending}>
                Créer
              </Button>
            </SheetFooter>
          </form>
        </SheetContent>
      </Sheet>

      {/* Renommer */}
      <Sheet open={!!renameTarget} onOpenChange={(o) => !o && setRenameTarget(null)}>
        <SheetContent>
          <form
            className="flex h-full flex-col"
            onSubmit={(e) => {
              e.preventDefault();
              onRename();
            }}
          >
            <SheetHeader>
              <SheetTitle>Renommer le modèle</SheetTitle>
            </SheetHeader>
            <SheetBody>
              <div className="space-y-2">
                <Label htmlFor="tpl-rename">Nouveau nom</Label>
                <Input
                  id="tpl-rename"
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  autoFocus
                />
              </div>
            </SheetBody>
            <SheetFooter>
              <Button type="button" variant="secondary" onClick={() => setRenameTarget(null)}>
                Annuler
              </Button>
              <Button type="submit" disabled={renameTpl.isPending}>
                Renommer
              </Button>
            </SheetFooter>
          </form>
        </SheetContent>
      </Sheet>

      {/* Catégorie */}
      <Sheet open={!!categoryTarget} onOpenChange={(o) => !o && setCategoryTarget(null)}>
        <SheetContent>
          <form
            className="flex h-full flex-col"
            onSubmit={(e) => {
              e.preventDefault();
              onSaveCategory();
            }}
          >
            <SheetHeader>
              <SheetTitle>Catégorie du modèle</SheetTitle>
              <SheetDescription>
                Texte libre. Laisser vide pour retirer la catégorie.
              </SheetDescription>
            </SheetHeader>
            <SheetBody>
              <div className="space-y-2">
                <Label htmlFor="tpl-cat">Catégorie</Label>
                <CategoryField id="tpl-cat" value={categoryValue} onChange={setCategoryValue} />
              </div>
            </SheetBody>
            <SheetFooter>
              <Button type="button" variant="secondary" onClick={() => setCategoryTarget(null)}>
                Annuler
              </Button>
              <Button type="submit" disabled={setCategory.isPending}>
                Enregistrer
              </Button>
            </SheetFooter>
          </form>
        </SheetContent>
      </Sheet>

      {/* Modification Catégorie */}
      <Sheet open={!!editCategoryTarget} onOpenChange={(o) => !o && setEditCategoryTarget(null)}>
        <SheetContent className="sm:max-w-[500px]">
          <form
            className="flex h-full flex-col"
            onSubmit={(e) => {
              e.preventDefault();
              onSaveCategoryDetails();
            }}
          >
            <SheetHeader>
              <SheetTitle>Modifier la catégorie</SheetTitle>
              <SheetDescription>
                Personnalisez la couleur et le message WhatsApp pour la catégorie <span className="font-semibold">{editCategoryTarget?.nom}</span>.
              </SheetDescription>
            </SheetHeader>
            <SheetBody className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="cat-color">Couleur (Hex)</Label>
                  <div className="flex gap-2">
                    <Input
                      type="color"
                      className="size-10 p-1 cursor-pointer"
                      value={editCategoryColor.startsWith('#') && editCategoryColor.length === 7 ? editCategoryColor : '#94a3b8'}
                      onChange={(e) => setEditCategoryColor(e.target.value)}
                    />
                    <Input
                      id="cat-color"
                      value={editCategoryColor}
                      onChange={(e) => setEditCategoryColor(e.target.value)}
                      placeholder="#94a3b8"
                      className="flex-1"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cat-order">Ordre de tri</Label>
                  <Input
                    id="cat-order"
                    type="number"
                    value={editCategoryOrder}
                    onChange={(e) => setEditCategoryOrder(parseInt(e.target.value, 10) || 0)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="cat-icon">Nom de l'icône Lucide (optionnel)</Label>
                <Input
                  id="cat-icon"
                  value={editCategoryIcon}
                  onChange={(e) => setEditCategoryIcon(e.target.value)}
                  placeholder="ex. Folder, FileText, etc."
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="cat-wa-msg">Message WhatsApp de partage</Label>
                  <span className="text-[10px] text-muted">
                    Variables : &lt;PRENOM&gt;, &lt;NOM&gt;, &lt;DOCUMENT&gt;
                  </span>
                </div>
                <textarea
                  id="cat-wa-msg"
                  className="w-full min-h-[120px] rounded-md border border-line bg-bg p-2 text-sm text-ink focus-ring"
                  value={editCategoryWhatsApp}
                  onChange={(e) => setEditCategoryWhatsApp(e.target.value)}
                  placeholder={`Par défaut : ${fallbackMessage}`}
                />
                <p className="text-[11px] text-muted">
                  Si ce message est vide, le message général de repli ci-dessus sera utilisé.
                </p>
              </div>
            </SheetBody>
            <SheetFooter>
              <Button type="button" variant="secondary" onClick={() => setEditCategoryTarget(null)}>
                Annuler
              </Button>
              <Button type="submit" disabled={updateCategory.isPending}>
                Enregistrer
              </Button>
            </SheetFooter>
          </form>
        </SheetContent>
      </Sheet>

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
