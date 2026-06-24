import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Check, Plus, Search, Trash2, Truck, Wallet, X } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Pagination } from "@/components/common/Pagination";
import { MoneySummary } from "@/components/common/MoneySummary";
import { DateRangeFilter } from "@/components/common/DateRangeFilter";
import { DepenseDialog } from "@/components/dialogs/DepenseDialog";
import { ReglerDepenseDialog } from "@/components/dialogs/ReglerDepenseDialog";
import { humanizeError } from "@/lib/errors";
import { depenseStatut, fmtEuro, isoToFr, modeLabel, monthRange } from "@/lib/format";
import {
  useAnnulerNote,
  useEncaisserNote,
  useFinanceDepenses,
  useFinancePaiements,
  type FinFilter,
} from "@/hooks/finances";
import { useDeleteDepense } from "@/hooks/prestataires";
import type { Depense } from "@/api/types";

/**
 * Écran Finances : reprend les deux sous-vues de l'app Flet (Paiements à
 * recouvrer / encaissés, Dépenses fournisseurs) avec filtres période + statut.
 */
export function Finances() {
  return (
    <div className="mx-auto max-w-6xl p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Finances</h1>
        <p className="mt-1 text-sm text-muted">
          Suivi des encaissements patients et des dépenses fournisseurs.
        </p>
      </header>

      <Tabs defaultValue="paiements">
        <TabsList>
          <TabsTrigger value="paiements">
            <Wallet className="size-4" /> Paiements
          </TabsTrigger>
          <TabsTrigger value="depenses">
            <Truck className="size-4" /> Dépenses
          </TabsTrigger>
        </TabsList>

        <TabsContent value="paiements">
          <PaiementsTab />
        </TabsContent>
        <TabsContent value="depenses">
          <DepensesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// --- Onglet Paiements --------------------------------------------------------

function PaiementsTab() {
  const [statut, setStatut] = useState("en_attente");
  const [search, setSearch] = useState("");
  const [range, setRange] = useState(monthRange);
  const [page, setPage] = useState(0);

  const filter: FinFilter = {
    statut,
    search,
    date_from: range.from,
    date_to: range.to,
  };
  const q = useFinancePaiements(filter, page);
  const encaisser = useEncaisserNote();
  const annuler = useAnnulerNote();

  const items = q.data?.items ?? [];
  const summary = q.data?.summary;

  function onEncaisser(id: number) {
    encaisser.mutate(
      { id },
      {
        onSuccess: () => toast.success("Note marquée encaissée."),
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  function onAnnuler(id: number) {
    annuler.mutate(id, {
      onSuccess: () => toast.success("Note annulée."),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-48 flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input
            className="pl-9"
            placeholder="Rechercher un patient…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
        </div>
        <Select
          value={statut}
          onValueChange={(v) => {
            setStatut(v);
            setPage(0);
          }}
        >
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="en_attente">À recouvrer</SelectItem>
            <SelectItem value="encaisse">Encaissés</SelectItem>
            <SelectItem value="tous">Tous</SelectItem>
          </SelectContent>
        </Select>
        <DateRangeFilter
          from={range.from}
          to={range.to}
          onChange={(r) => {
            setRange(r);
            setPage(0);
          }}
        />
      </div>

      {q.isError && <p className="text-sm text-red">{humanizeError(q.error)}</p>}

      {summary && (
        <MoneySummary
          items={[
            {
              label: summary.label,
              value: summary.total,
              tone: statut === "encaisse" ? "green" : "amber",
            },
          ]}
        />
      )}

      <div className="rounded-[var(--radius)] border border-line bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-right">Montant</TableHead>
              <TableHead>Patient</TableHead>
              <TableHead>Détail</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((row) => {
              const isNote = row.kind === "paiement";
              const enAttente = row.statut === "en_attente";
              const encaisse = row.statut === "encaisse";
              const detail = [
                row.libelle,
                isoToFr(row.date),
                row.mode ? modeLabel(row.mode) : "",
              ]
                .filter(Boolean)
                .join(" · ");
              return (
                <TableRow key={`${row.kind}-${row.source_id}`}>
                  <TableCell className="text-right font-semibold tabular-nums">
                    {fmtEuro(row.montant)}
                  </TableCell>
                  <TableCell className="font-semibold">{row.patient_display}</TableCell>
                  <TableCell className="text-muted">{detail || "—"}</TableCell>
                  <TableCell>
                    {encaisse ? (
                      <Badge variant="success">Encaissé</Badge>
                    ) : (
                      <Badge variant="default">En attente</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
                      {isNote && enAttente && (
                        <>
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Marquer encaissé"
                            className="text-green"
                            disabled={encaisser.isPending}
                            onClick={() => onEncaisser(row.source_id)}
                          >
                            <Check className="size-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Annuler"
                            className="text-red"
                            disabled={annuler.isPending}
                            onClick={() => onAnnuler(row.source_id)}
                          >
                            <X className="size-4" />
                          </Button>
                        </>
                      )}
                      <Button variant="secondary" size="sm" asChild>
                        <Link to={`/patients/${row.patient_id}`}>Ouvrir la fiche</Link>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
            {!q.isLoading && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-6 text-center text-muted">
                  Aucun paiement.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Pagination total={q.data?.total ?? 0} page={page} onPage={setPage} />
    </div>
  );
}

// --- Onglet Dépenses ---------------------------------------------------------

function DepensesTab() {
  const [statut, setStatut] = useState("en_attente");
  const [search, setSearch] = useState("");
  const [range, setRange] = useState(monthRange);
  const [page, setPage] = useState(0);
  const [newOpen, setNewOpen] = useState(false);
  const [regler, setRegler] = useState<Depense | null>(null);

  const filter: FinFilter = {
    statut,
    search,
    date_from: range.from,
    date_to: range.to,
  };
  const q = useFinanceDepenses(filter, page);
  const del = useDeleteDepense();

  const items = q.data?.items ?? [];
  const summary = q.data?.summary;

  function onDelete(id: number) {
    del.mutate(id, {
      onSuccess: () => toast.success("Dépense supprimée."),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
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
        <Select
          value={statut}
          onValueChange={(v) => {
            setStatut(v);
            setPage(0);
          }}
        >
          <SelectTrigger className="w-52">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="en_attente">À régler</SelectItem>
            <SelectItem value="regle_partiellement">Réglé partiellement</SelectItem>
            <SelectItem value="regle">Réglé</SelectItem>
            <SelectItem value="tous">Tous</SelectItem>
          </SelectContent>
        </Select>
        <DateRangeFilter
          from={range.from}
          to={range.to}
          onChange={(r) => {
            setRange(r);
            setPage(0);
          }}
        />
        <Button onClick={() => setNewOpen(true)}>
          <Plus className="size-4" /> Nouvelle dépense
        </Button>
      </div>

      {q.isError && <p className="text-sm text-red">{humanizeError(q.error)}</p>}

      {summary && (
        <MoneySummary
          items={[
            { label: "Total dû", value: summary.du },
            { label: "Réglé", value: summary.regle, tone: "green" },
            { label: "Reste à payer", value: summary.reste, tone: "amber" },
          ]}
        />
      )}

      <div className="rounded-[var(--radius)] border border-line bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-right">Montant</TableHead>
              <TableHead>Prestataire</TableHead>
              <TableHead>Échéance / Dernier règlement</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((row) => {
              const d = row.depense;
              const st = depenseStatut(d.statut);
              const dateRef = d.date_paiement ?? d.date_echeance;
              return (
                <TableRow key={d.id}>
                  <TableCell className="text-right">
                    <div className="font-semibold tabular-nums">{fmtEuro(d.montant)}</div>
                    <div className="text-xs text-muted tabular-nums">
                      réglé {fmtEuro(d.montant_regle)} · reste {fmtEuro(d.reste)}
                    </div>
                  </TableCell>
                  <TableCell className="font-semibold">
                    <Link
                      to={`/prestataires/${row.prestataire_id}`}
                      className="text-navy hover:underline"
                    >
                      {row.prestataire_display}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted">{isoToFr(dateRef) || "—"}</TableCell>
                  <TableCell>
                    <Badge variant={st.variant}>{st.label}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
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
                        disabled={del.isPending}
                        onClick={() => onDelete(d.id)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
            {!q.isLoading && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="py-6 text-center text-muted">
                  Aucune dépense.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Pagination total={q.data?.total ?? 0} page={page} onPage={setPage} />

      <DepenseDialog open={newOpen} onClose={() => setNewOpen(false)} />
      <ReglerDepenseDialog depense={regler} onClose={() => setRegler(null)} />
    </div>
  );
}
