import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, Plus, Search, Store } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/common/Pagination";
import { PrestataireFormDialog } from "@/components/dialogs/PrestataireFormDialog";
import { humanizeError } from "@/lib/errors";
import { usePrestataires } from "@/hooks/prestataires";

/**
 * Liste des prestataires (fournisseurs). Reprend la liste Flet : recherche +
 * création, lignes cliquables menant à la fiche détaillée.
 */
export function Prestataires() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [showNew, setShowNew] = useState(false);

  const list = usePrestataires(search, page);
  const items = list.data?.items ?? [];

  return (
    <div className="mx-auto max-w-5xl p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Prestataires</h1>
        <p className="mt-1 text-sm text-muted">
          Fournisseurs et laboratoires : factures et dépenses associées.
        </p>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-48 flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input
            className="pl-9"
            placeholder="Rechercher un prestataire…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
        </div>
        <Button onClick={() => setShowNew(true)}>
          <Plus className="size-4" /> Nouveau prestataire
        </Button>
      </div>

      {list.isLoading && <p className="text-sm text-muted">Chargement…</p>}
      {list.isError && <p className="text-sm text-red">{humanizeError(list.error)}</p>}

      <div className="overflow-hidden rounded-[var(--radius)] border border-line bg-white">
        <ul className="divide-y divide-line">
          {items.map((p) => {
            const sub = [p.email, p.telephone].filter(Boolean).join(" · ");
            return (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => navigate(`/prestataires/${p.id}`)}
                  className="flex w-full items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-bg"
                >
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-navy/10 text-navy">
                    <Store className="size-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-semibold text-ink">{p.display}</div>
                    <div className="truncate text-sm text-muted">{sub || "—"}</div>
                  </div>
                  <span className="shrink-0 text-xs text-muted tabular-nums">#{p.id}</span>
                  <ChevronRight className="size-4 shrink-0 text-muted" />
                </button>
              </li>
            );
          })}
          {!list.isLoading && items.length === 0 && (
            <li className="py-6 text-center text-sm text-muted">Aucun prestataire.</li>
          )}
        </ul>
      </div>

      <div className="mt-4">
        <Pagination total={list.data?.total ?? 0} page={page} onPage={setPage} />
      </div>

      {showNew && (
        <PrestataireFormDialog
          target="new"
          onClose={() => setShowNew(false)}
          onCreated={(p) => navigate(`/prestataires/${p.id}`)}
        />
      )}
    </div>
  );
}
