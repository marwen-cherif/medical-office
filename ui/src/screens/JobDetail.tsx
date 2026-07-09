import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, FolderOpen, Printer, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/common/Tooltip";
import { humanizeError } from "@/lib/errors";
import { useShortcut } from "@/lib/shortcuts";
import { humanize, JOB_ITEM_STATUTS, jobStatut } from "@/lib/format";
import { useJob, useRelaunchJob } from "@/hooks/jobs";
import { useOpenDocument, usePrintDocument } from "@/hooks/documents";

/**
 * Détail d'un job (route /travaux/jobs/:id) : synthèse de progression + liste
 * ligne par patient, avec relance des erreurs et actions sur les fichiers générés.
 */
export function JobDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id ? Number(params.id) : null;
  const navigate = useNavigate();

  const q = useJob(id);
  const relaunch = useRelaunchJob();
  const open = useOpenDocument();
  const print = usePrintDocument();

  function onOpen(docId: number) {
    open.mutate(docId, { onError: (e) => toast.error(humanizeError(e)) });
  }

  function onPrint(docId: number) {
    print.mutate(
      { id: docId },
      {
        onSuccess: () => toast.success("Document envoyé à l'impression."),
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  function onRelaunch(jobId: number) {
    relaunch.mutate(
      { id: jobId },
      {
        onSuccess: () => toast.success("Relance des erreurs lancée."),
        onError: (e) => toast.error(humanizeError(e)),
      },
    );
  }

  const canRelaunch = !!q.data && q.data.job.errors > 0 && q.data.job.statut !== "en_cours";
  useShortcut({
    keys: "alt+r",
    description: "Relancer les erreurs",
    group: "Travaux",
    enabled: canRelaunch && !relaunch.isPending,
    handler: () => q.data && onRelaunch(q.data.job.id),
  });

  return (
    <div className="mx-auto max-w-4xl p-8">
      <Button variant="ghost" size="sm" className="mb-4" onClick={() => navigate("/travaux")}>
        <ArrowLeft className="size-4" /> Retour
      </Button>

      {q.isLoading && <p className="text-sm text-muted">Chargement…</p>}
      {q.isError && <p className="text-sm text-red">{humanizeError(q.error)}</p>}
      {!q.isLoading && !q.isError && !q.data && (
        <p className="text-sm text-muted">Job introuvable.</p>
      )}

      {q.data && (
        <JobDetailBody
          job={q.data.job}
          items={q.data.items}
          onRelaunch={onRelaunch}
          relaunchPending={relaunch.isPending}
          onOpen={onOpen}
          onPrint={onPrint}
        />
      )}
    </div>
  );
}

function JobDetailBody({
  job,
  items,
  onRelaunch,
  relaunchPending,
  onOpen,
  onPrint,
}: {
  job: NonNullable<ReturnType<typeof useJob>["data"]>["job"];
  items: NonNullable<ReturnType<typeof useJob>["data"]>["items"];
  onRelaunch: (jobId: number) => void;
  relaunchPending: boolean;
  onOpen: (docId: number) => void;
  onPrint: (docId: number) => void;
}) {
  const st = jobStatut(job.statut);
  const isGen = job.kind === "generation";
  const pct = job.total > 0 ? Math.round((job.done / job.total) * 100) : 0;
  const canRelaunch = job.errors > 0 && job.statut !== "en_cours";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-2xl font-semibold text-ink">
          Job #{job.id} — {isGen ? "Génération" : "Envoi email"} · {humanize(job.doc_type)}
        </h1>
        {canRelaunch && (
          <Tooltip label="Relancer les erreurs" shortcut="alt+r">
            <Button
              variant="secondary"
              disabled={relaunchPending}
              onClick={() => onRelaunch(job.id)}
            >
              <RotateCcw className="size-4" /> Relancer les erreurs
            </Button>
          </Tooltip>
        )}
      </div>

      <div className="space-y-3 rounded-[var(--radius)] border border-line bg-white p-5">
        <div className="flex items-center justify-between">
          <Badge variant={st.variant}>{st.label}</Badge>
          <span className="text-sm tabular-nums text-muted">
            {job.done}/{job.total}
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-line">
          <div className="h-full rounded-full bg-navy" style={{ width: `${pct}%` }} />
        </div>
        <div className="text-sm text-muted">
          {job.ok} ok · {job.skipped} ignoré(s) · {job.errors} erreur(s)
        </div>
      </div>

      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-ink">Détail par patient</h2>
        <div className="space-y-2">
          {items.map((item) => {
            const ist = JOB_ITEM_STATUTS[item.statut] ?? {
              label: humanize(item.statut),
              variant: "muted" as const,
            };
            return (
              <div
                key={item.id}
                className="flex items-center gap-3 rounded-[var(--radius)] border border-line bg-white px-4 py-3"
              >
                <Badge variant={ist.variant}>{ist.label}</Badge>
                <div className="min-w-0 flex-1">
                  {item.patient_id != null ? (
                    <Link
                      to={`/patients/${item.patient_id}`}
                      className="font-semibold text-navy hover:underline"
                    >
                      {item.patient_display ?? `Patient #${item.patient_id}`}
                    </Link>
                  ) : (
                    <span className="font-semibold text-ink">
                      {item.patient_display ?? "—"}
                    </span>
                  )}
                  {item.message && (
                    <div
                      className={
                        item.statut === "erreur"
                          ? "text-xs text-red"
                          : "text-xs text-muted"
                      }
                    >
                      {item.message}
                    </div>
                  )}
                </div>
                {item.has_file && item.document_id != null && (
                  <div className="flex shrink-0 items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Ouvrir"
                      onClick={() => onOpen(item.document_id!)}
                    >
                      <FolderOpen className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Imprimer"
                      onClick={() => onPrint(item.document_id!)}
                    >
                      <Printer className="size-4" />
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
          {items.length === 0 && (
            <p className="rounded-[var(--radius)] border border-line bg-white py-6 text-center text-sm text-muted">
              Aucune ligne.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
