import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ChevronRight,
  FileText,
  FolderOpen,
  Hammer,
  Image as ImageIcon,
  Mail,
  PlayCircle,
  Printer,
  Send,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
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
import { DateRangeFilter } from "@/components/common/DateRangeFilter";
import { humanizeError } from "@/lib/errors";
import {
  docStatut,
  fmtDevise,
  humanize,
  isoToFr,
  isoToFrDateTime,
  jobStatut,
  monthRange,
} from "@/lib/format";
import {
  useDocumentsFiltered,
  useOpenDocument,
  usePrintDocument,
  useRenderDocument,
  useSendDocument,
  type DocFilter,
} from "@/hooks/documents";
import { useBatch, useJobs, type JobFilter } from "@/hooks/jobs";
import type { DocumentRow } from "@/api/types";

/**
 * Écran Travaux : reprend l'écran « Documents/Travaux » de l'app Flet avec deux
 * onglets — la liste plate des documents (avec actions unitaires et traitements
 * par lot) et la liste des jobs de génération/envoi par lot.
 */
export function Travaux() {
  return (
    <div className="mx-auto max-w-6xl p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Travaux</h1>
        <p className="mt-1 text-sm text-muted">
          Documents générés et jobs de traitement par lot.
        </p>
      </header>

      <Tabs defaultValue="documents">
        <TabsList>
          <TabsTrigger value="documents">
            <FileText className="size-4" /> Documents
          </TabsTrigger>
          <TabsTrigger value="jobs">
            <Hammer className="size-4" /> Travaux
          </TabsTrigger>
        </TabsList>

        <TabsContent value="documents">
          <DocumentsTab />
        </TabsContent>
        <TabsContent value="jobs">
          <JobsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// --- Onglet Documents --------------------------------------------------------

const STATUT_OPTIONS = [
  { value: "tous", label: "Tous les statuts" },
  { value: "brouillon", label: "Brouillon" },
  { value: "genere", label: "Généré" },
  { value: "en_attente_envoi", label: "En attente d'envoi" },
  { value: "envoye", label: "Envoyé" },
  { value: "erreur", label: "Erreur génération" },
  { value: "erreur_envoi", label: "Erreur envoi" },
];

/** Statuts pour lesquels la sélection multiple + traitement par lot s'applique. */
function batchKindFor(statut: string): "generation" | "envoi" | null {
  if (statut === "brouillon" || statut === "erreur") return "generation";
  if (statut === "en_attente_envoi" || statut === "erreur_envoi") return "envoi";
  return null;
}

function DocumentsTab() {
  const [search, setSearch] = useState("");
  const [statut, setStatut] = useState("tous");
  const [range, setRange] = useState(monthRange);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const filter: DocFilter = {
    search,
    statut: statut === "tous" ? "" : statut,
    date_from: range.from,
    date_to: range.to,
  };
  const q = useDocumentsFiltered(filter, page);

  const render = useRenderDocument();
  const open = useOpenDocument();
  const print = usePrintDocument();
  const send = useSendDocument();
  const batch = useBatch();

  const items = q.data?.items ?? [];
  const batchKind = batchKindFor(statut);
  const selectable = batchKind != null;

  // Ids visibles sélectionnables (la sélection ne porte que sur la page courante).
  const visibleIds = useMemo(() => items.map((r) => r.document.id), [items]);
  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selected.has(id));

  function resetPageAnd(fn: () => void) {
    fn();
    setPage(0);
    setSelected(new Set());
  }

  function toggleOne(id: number, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    setSelected(checked ? new Set(visibleIds) : new Set());
  }

  function onRender(id: number) {
    render.mutate(
      { id },
      {
        onSuccess: () => toast.success("Document généré."),
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  function onOpen(id: number) {
    open.mutate(id, { onError: (e) => toast.error(humanizeError(e)) });
  }

  function onPrint(id: number) {
    print.mutate(
      { id },
      {
        onSuccess: () => toast.success("Document envoyé à l'impression."),
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  function onSend(id: number) {
    send.mutate(
      { id, body: {} },
      {
        onSuccess: () => toast.success("Document envoyé."),
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  function onBatch() {
    if (!batchKind) return;
    const ids = [...selected];
    if (ids.length === 0) return;
    batch.mutate(
      { kind: batchKind, documentIds: ids },
      {
        onSuccess: () =>
          toast.success(
            batchKind === "generation"
              ? `${ids.length} document(s) traité(s).`
              : `${ids.length} envoi(s) traité(s).`,
          ),
        onError: (e) => toast.error(humanizeError(e)),
        onSettled: () => setSelected(new Set()),
      },
    );
  }

  const colSpan = selectable ? 5 : 4;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        Toutes les lignes de documents. Cliquez le nom du patient pour ouvrir sa fiche.
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-48 flex-1">
          <Input
            placeholder="Rechercher un patient…"
            value={search}
            onChange={(e) => resetPageAnd(() => setSearch(e.target.value))}
          />
        </div>
        <Select value={statut} onValueChange={(v) => resetPageAnd(() => setStatut(v))}>
          <SelectTrigger className="w-52">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUT_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <DateRangeFilter
          from={range.from}
          to={range.to}
          onChange={(r) => resetPageAnd(() => setRange(r))}
        />
      </div>

      {selectable && (
        <div className="flex items-center justify-between rounded-[var(--radius)] border border-line bg-bg/50 px-4 py-2">
          <span className="text-sm text-muted">
            {selected.size} document(s) sélectionné(s)
          </span>
          <Button
            size="sm"
            disabled={selected.size === 0 || batch.isPending}
            onClick={onBatch}
          >
            {batchKind === "generation" ? (
              <>
                <PlayCircle className="size-4" /> Générer la sélection
              </>
            ) : (
              <>
                <Send className="size-4" /> Envoyer la sélection
              </>
            )}
          </Button>
        </div>
      )}

      {q.isError && <p className="text-sm text-red">{humanizeError(q.error)}</p>}

      <div className="rounded-[var(--radius)] border border-line bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              {selectable && (
                <TableHead className="w-10">
                  <Checkbox
                    checked={allVisibleSelected}
                    onCheckedChange={toggleAll}
                    aria-label="Tout sélectionner"
                  />
                </TableHead>
              )}
              <TableHead>Patient</TableHead>
              <TableHead>Détail</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((row) => (
              <DocumentRowItem
                key={row.document.id}
                row={row}
                selectable={selectable}
                selected={selected.has(row.document.id)}
                onToggle={(checked) => toggleOne(row.document.id, checked)}
                onRender={onRender}
                onOpen={onOpen}
                onPrint={onPrint}
                onSend={onSend}
                pendingRender={render.isPending}
                pendingSend={send.isPending}
              />
            ))}
            {!q.isLoading && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={colSpan} className="py-6 text-center text-muted">
                  Aucun document.
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

function DocumentRowItem({
  row,
  selectable,
  selected,
  onToggle,
  onRender,
  onOpen,
  onPrint,
  onSend,
  pendingRender,
  pendingSend,
}: {
  row: DocumentRow;
  selectable: boolean;
  selected: boolean;
  onToggle: (checked: boolean) => void;
  onRender: (id: number) => void;
  onOpen: (id: number) => void;
  onPrint: (id: number) => void;
  onSend: (id: number) => void;
  pendingRender: boolean;
  pendingSend: boolean;
}) {
  const d = row.document;
  const st = docStatut(d.statut);
  const isPdf = (d.output_format ?? "").toLowerCase() === "pdf";
  const FormatIcon = isPdf ? FileText : ImageIcon;
  const dateRef = d.date_envoi ?? d.date_generation;

  const needsGeneration = d.statut === "brouillon" || d.statut === "erreur";
  const canSend =
    !!d.email && (d.statut === "en_attente_envoi" || d.statut === "erreur_envoi");

  return (
    <TableRow>
      {selectable && (
        <TableCell className="w-10">
          <Checkbox
            checked={selected}
            onCheckedChange={onToggle}
            aria-label="Sélectionner le document"
          />
        </TableCell>
      )}
      <TableCell>
        <div className="flex items-center gap-3">
          <FormatIcon className="size-5 shrink-0 text-muted" />
          <div className="min-w-0">
            <Link
              to={`/patients/${d.patient_id}`}
              className="font-semibold text-navy hover:underline"
            >
              {row.patient.display}
            </Link>
            <div className="text-xs text-muted">
              {[humanize(d.type), isoToFr(dateRef)].filter(Boolean).join(" · ")}
            </div>
          </div>
        </div>
      </TableCell>
      <TableCell className="text-muted">
        {[humanize(d.type), d.montant != null ? fmtDevise(d.montant) : ""]
          .filter(Boolean)
          .join(" · ") || "—"}
      </TableCell>
      <TableCell>
        <Badge variant={st.variant}>{st.label}</Badge>
      </TableCell>
      <TableCell>
        <div className="flex items-center justify-end gap-1">
          {needsGeneration ? (
            <Button
              variant="ghost"
              size="icon"
              title={d.statut === "erreur" ? "Réessayer" : "Générer"}
              disabled={pendingRender}
              onClick={() => onRender(d.id)}
            >
              <PlayCircle className="size-4" />
            </Button>
          ) : (
            d.has_file && (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  title="Ouvrir"
                  onClick={() => onOpen(d.id)}
                >
                  <FolderOpen className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  title="Imprimer"
                  onClick={() => onPrint(d.id)}
                >
                  <Printer className="size-4" />
                </Button>
              </>
            )
          )}
          {canSend && (
            <Button
              variant="ghost"
              size="icon"
              title="Envoyer"
              className="text-navy"
              disabled={pendingSend}
              onClick={() => onSend(d.id)}
            >
              <Send className="size-4" />
            </Button>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

// --- Onglet Travaux (jobs) ---------------------------------------------------

function JobsTab() {
  const navigate = useNavigate();
  const [range, setRange] = useState(monthRange);
  const [page, setPage] = useState(0);

  const filter: JobFilter = { date_from: range.from, date_to: range.to };
  const q = useJobs(filter, page);
  const items = q.data?.items ?? [];

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        Jobs de génération et d'envoi par lot. Cliquez un job pour voir le détail (ligne par
        patient).
      </p>

      <div className="flex flex-wrap items-center gap-3">
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

      <div className="space-y-2">
        {items.map((job) => {
          const st = jobStatut(job.statut);
          const isGen = job.kind === "generation";
          const JobIcon = isGen ? Hammer : Mail;
          const pct = job.total > 0 ? Math.round((job.done / job.total) * 100) : 0;
          return (
            <button
              key={job.id}
              type="button"
              onClick={() => navigate(`/travaux/jobs/${job.id}`)}
              className="flex w-full items-center gap-4 rounded-[var(--radius)] border border-line bg-white px-4 py-3 text-left transition-colors hover:bg-bg/60"
            >
              <JobIcon className="size-6 shrink-0 text-navy" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-semibold text-ink">
                    #{job.id} · {isGen ? "Génération" : "Envoi email"} —{" "}
                    {humanize(job.doc_type)}
                  </span>
                  <Badge variant={st.variant}>{st.label}</Badge>
                </div>
                <div className="mt-0.5 text-xs text-muted">
                  {job.done}/{job.total} traité(s) · {job.ok} ok · {job.skipped} ignoré(s) ·{" "}
                  {job.errors} erreur(s)
                </div>
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-line">
                  <div className="h-full rounded-full bg-navy" style={{ width: `${pct}%` }} />
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2 text-xs text-muted">
                <span>{isoToFrDateTime(job.created_at)}</span>
                <ChevronRight className="size-4" />
              </div>
            </button>
          );
        })}
        {!q.isLoading && items.length === 0 && (
          <p className="rounded-[var(--radius)] border border-line bg-white py-6 text-center text-sm text-muted">
            Aucun job.
          </p>
        )}
      </div>

      <Pagination total={q.data?.total ?? 0} page={page} onPage={setPage} />
    </div>
  );
}
