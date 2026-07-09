import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Check, FolderOpen, Plus, Receipt, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/common/Pagination";
import { MoneySummary } from "@/components/common/MoneySummary";
import { Tooltip } from "@/components/common/Tooltip";
import { PrestataireFormDialog } from "@/components/dialogs/PrestataireFormDialog";
import { DepenseDialog } from "@/components/dialogs/DepenseDialog";
import { ReglerDepenseDialog } from "@/components/dialogs/ReglerDepenseDialog";
import { ImportFactureDialog } from "@/components/dialogs/ImportFactureDialog";
import { humanizeError } from "@/lib/errors";
import { useShortcut } from "@/lib/shortcuts";
import { depenseStatut, fmtDevise, isoToFr } from "@/lib/format";
import { Montant } from "@/components/common/Montant";
import {
  useDeleteDepense,
  useDeleteFacture,
  useFactures,
  useOpenFacture,
  usePrestataire,
  useProviderDepenses,
} from "@/hooks/prestataires";
import type { Depense, Prestataire } from "@/api/types";

/** Fiche prestataire : identité, récap monétaire, factures et dépenses. */
export function PrestataireDetail() {
  const params = useParams();
  const id = Number(params.id);
  const navigate = useNavigate();

  const detailQ = usePrestataire(id);
  const [edit, setEdit] = useState<Prestataire | null>(null);

  useShortcut({
    keys: "alt+e",
    description: "Modifier le prestataire",
    group: "Fiche prestataire",
    enabled: !!detailQ.data,
    handler: () => detailQ.data && setEdit(detailQ.data.prestataire),
  });

  if (detailQ.isLoading) {
    return <p className="mx-auto max-w-5xl p-8 text-sm text-muted">Chargement…</p>;
  }
  if (detailQ.isError) {
    return (
      <p className="mx-auto max-w-5xl p-8 text-sm text-red">{humanizeError(detailQ.error)}</p>
    );
  }
  const detail = detailQ.data;
  if (!detail) {
    return <p className="mx-auto max-w-5xl p-8 text-sm text-muted">Prestataire introuvable.</p>;
  }

  const p = detail.prestataire;
  const s = detail.summary;

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="mb-6 flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Retour"
          onClick={() => navigate("/prestataires")}
        >
          <ArrowLeft className="size-4" />
        </Button>
        <h1 className="flex-1 text-2xl font-semibold text-ink">{p.display}</h1>
        <Tooltip label="Modifier le prestataire" shortcut="alt+e">
          <Button variant="secondary" onClick={() => setEdit(p)}>
            Modifier
          </Button>
        </Tooltip>
      </div>

      <IdentityCard p={p} />

      <div className="mt-4">
        <MoneySummary
          items={[
            { label: "Total dû", value: s.du },
            { label: "Réglé", value: s.regle, tone: "green" },
            { label: "Reste à payer", value: s.reste, tone: "amber" },
          ]}
        />
      </div>

      <FacturesSection id={id} />
      <DepensesSection id={id} />

      {edit && (
        <PrestataireFormDialog target={edit} onClose={() => setEdit(null)} />
      )}
    </div>
  );
}

// --- Carte identité ----------------------------------------------------------

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex gap-3 py-1.5 text-sm">
      <span className="w-28 shrink-0 text-muted">{label}</span>
      <span className="min-w-0 flex-1 break-words text-ink">{value || "—"}</span>
    </div>
  );
}

function IdentityCard({ p }: { p: Prestataire }) {
  return (
    <div className="rounded-[var(--radius)] border border-line bg-white p-5">
      <Row label="Email" value={p.email} />
      <Row label="Téléphone" value={p.telephone} />
      <Row label="Adresse" value={p.adresse} />
      <Row label="Notes" value={p.notes} />
    </div>
  );
}

// --- Section factures --------------------------------------------------------

function FacturesSection({ id }: { id: number }) {
  const [page, setPage] = useState(0);
  const facturesQ = useFactures(id, page);
  const delFacture = useDeleteFacture(id);
  const openFacture = useOpenFacture();
  const fileRef = useRef<HTMLInputElement>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const items = facturesQ.data?.items ?? [];

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) setPendingFile(file);
  }

  function onOpen(factureId: number) {
    openFacture.mutate(factureId, {
      onError: (err) => toast.error(humanizeError(err)),
    });
  }

  function onDelete(factureId: number) {
    delFacture.mutate(factureId, {
      onSuccess: () => toast.success("Facture supprimée."),
      onError: (err) => toast.error(humanizeError(err)),
    });
  }

  return (
    <section className="mt-8">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">Factures</h2>
        <Button variant="secondary" onClick={() => fileRef.current?.click()}>
          <Upload className="size-4" /> Importer une facture
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          className="hidden"
          onChange={onPick}
        />
      </div>

      {facturesQ.isError && (
        <p className="text-sm text-red">{humanizeError(facturesQ.error)}</p>
      )}

      <div className="overflow-hidden rounded-[var(--radius)] border border-line bg-white">
        <ul className="divide-y divide-line">
          {items.map((f) => {
            const sub = [isoToFr(f.created_at), f.montant != null ? fmtDevise(f.montant) : ""]
              .filter(Boolean)
              .join(" · ");
            return (
              <li key={f.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-navy/10 text-navy">
                  <Receipt className="size-4" />
                </div>
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  title="Ouvrir la facture"
                  onClick={() => onOpen(f.id)}
                >
                  <div className="truncate font-medium text-ink hover:underline">
                    {f.nom_original || f.fichier}
                  </div>
                  <div className="truncate text-sm text-muted">{sub || "—"}</div>
                </button>
                <Button
                  variant="ghost"
                  size="icon"
                  title="Ouvrir la facture"
                  disabled={openFacture.isPending}
                  onClick={() => onOpen(f.id)}
                >
                  <FolderOpen className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  title="Supprimer"
                  className="text-red"
                  disabled={delFacture.isPending}
                  onClick={() => onDelete(f.id)}
                >
                  <Trash2 className="size-4" />
                </Button>
              </li>
            );
          })}
          {!facturesQ.isLoading && items.length === 0 && (
            <li className="py-6 text-center text-sm text-muted">Aucune facture.</li>
          )}
        </ul>
      </div>

      <div className="mt-3">
        <Pagination total={facturesQ.data?.total ?? 0} page={page} onPage={setPage} />
      </div>

      <ImportFactureDialog
        file={pendingFile}
        prestataireId={id}
        onClose={() => setPendingFile(null)}
      />
    </section>
  );
}

// --- Section dépenses --------------------------------------------------------

function DepensesSection({ id }: { id: number }) {
  const [page, setPage] = useState(0);
  const [newOpen, setNewOpen] = useState(false);
  const [regler, setRegler] = useState<Depense | null>(null);

  const depensesQ = useProviderDepenses(id, page);
  const delDepense = useDeleteDepense(id);

  const items = depensesQ.data?.items ?? [];

  function onDelete(depenseId: number) {
    delDepense.mutate(depenseId, {
      onSuccess: () => toast.success("Dépense supprimée."),
      onError: (err) => toast.error(humanizeError(err)),
    });
  }

  return (
    <section className="mt-8">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">Dépenses</h2>
        <Button onClick={() => setNewOpen(true)}>
          <Plus className="size-4" /> Nouvelle dépense
        </Button>
      </div>

      {depensesQ.isError && (
        <p className="text-sm text-red">{humanizeError(depensesQ.error)}</p>
      )}

      <div className="overflow-hidden rounded-[var(--radius)] border border-line bg-white">
        <ul className="divide-y divide-line">
          {items.map((d) => {
            const st = depenseStatut(d.statut);
            const sub = [d.libelle, isoToFr(d.date_echeance)].filter(Boolean).join(" · ");
            return (
              <li key={d.id} className="flex items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <Montant value={d.montant} bold tone="ink" className="block" />
                  <div className="text-xs text-muted tabular-nums">
                    réglé {fmtDevise(d.montant_regle)} · reste {fmtDevise(d.reste)}
                  </div>
                  {sub && <div className="truncate text-sm text-muted">{sub}</div>}
                </div>
                <Badge variant={st.variant}>{st.label}</Badge>
                <div className="flex shrink-0 items-center gap-1">
                  {d.statut !== "regle" && (
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Régler"
                      className="text-green"
                      onClick={() => setRegler(d)}
                    >
                      <Check className="size-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Supprimer"
                    className="text-red"
                    disabled={delDepense.isPending}
                    onClick={() => onDelete(d.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </li>
            );
          })}
          {!depensesQ.isLoading && items.length === 0 && (
            <li className="py-6 text-center text-sm text-muted">Aucune dépense.</li>
          )}
        </ul>
      </div>

      <div className="mt-3">
        <Pagination total={depensesQ.data?.total ?? 0} page={page} onPage={setPage} />
      </div>

      <DepenseDialog open={newOpen} onClose={() => setNewOpen(false)} prestataireId={id} />
      <ReglerDepenseDialog depense={regler} prestataireId={id} onClose={() => setRegler(null)} />
    </section>
  );
}
