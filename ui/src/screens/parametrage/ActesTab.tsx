import { useState } from "react";
import { toast } from "sonner";
import { Pencil, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { humanizeError } from "@/lib/errors";
import { Montant } from "@/components/common/Montant";
import { useActes, useActeCategories, useSetActeActive } from "@/hooks/queries";
import type { Acte } from "@/api/types";
import { ActeFormDialog } from "./ActeFormDialog";
import { ActesImportExport } from "./ActesImportExport";

// Sentinelles du filtre déroulant (Radix Select interdit la valeur vide) :
//  - TOUTES  -> aucune restriction (categorie non transmise à l'API) ;
//  - SANS    -> actes sans catégorie (valeur reconnue côté serveur, repo.SANS_CATEGORIE).
const TOUTES = "__all__";
const SANS = "(sans)";

export function ActesTab() {
  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [categorie, setCategorie] = useState<string>(TOUTES);
  const list = useActes(search, includeInactive, categorie === TOUTES ? undefined : categorie);
  const cats = useActeCategories(includeInactive);
  const setActive = useSetActeActive();

  const [target, setTarget] = useState<Acte | "new" | null>(null);

  function openEditor(a: Acte | "new") {
    setTarget(a);
  }

  function onToggle(a: Acte) {
    setActive.mutate(
      { id: a.id, actif: !a.actif },
      {
        onSuccess: () => toast.success(a.actif ? "Acte désactivé." : "Acte activé."),
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input
            className="pl-9"
            placeholder="Rechercher un acte…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={categorie} onValueChange={setCategorie}>
          <SelectTrigger className="w-52">
            <SelectValue placeholder="Catégorie" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={TOUTES}>Toutes les catégories</SelectItem>
            <SelectItem value={SANS}>Sans catégorie</SelectItem>
            {(cats.data?.items ?? []).map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm text-ink">
          <Switch checked={includeInactive} onCheckedChange={setIncludeInactive} />
          Inclure les inactifs
        </label>
        <ActesImportExport includeInactive={includeInactive} />
        <Button onClick={() => openEditor("new")}>
          <Plus className="size-4" /> Nouvel acte
        </Button>
      </div>

      {list.isLoading && <p className="text-sm text-muted">Chargement…</p>}
      {list.isError && <p className="text-sm text-red">{humanizeError(list.error)}</p>}

      <div className="rounded-[var(--radius)] border border-line bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Libellé</TableHead>
              <TableHead>Code</TableHead>
              <TableHead>Catégorie</TableHead>
              <TableHead className="text-right">Prix</TableHead>
              <TableHead>État</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(list.data?.items ?? []).map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-medium">{a.libelle}</TableCell>
                <TableCell className="font-mono text-muted">{a.code ?? "—"}</TableCell>
                <TableCell>
                  {a.categorie ? (
                    <Badge variant="muted">{a.categorie}</Badge>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Montant value={a.prix} />
                </TableCell>
                <TableCell>
                  {a.actif ? (
                    <Badge variant="success">Actif</Badge>
                  ) : (
                    <Badge variant="muted">Inactif</Badge>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="ghost" size="icon" title="Modifier" onClick={() => openEditor(a)}>
                      <Pencil className="size-4" />
                    </Button>
                    <Switch
                      checked={a.actif}
                      onCheckedChange={() => onToggle(a)}
                      aria-label={a.actif ? "Désactiver" : "Activer"}
                    />
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {list.data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-6 text-center text-muted">
                  Aucun acte.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {list.data && (
        <p className="text-xs text-muted">{list.data.total} acte(s) au total.</p>
      )}

      <ActeFormDialog target={target} onClose={() => setTarget(null)} />
    </div>
  );
}
