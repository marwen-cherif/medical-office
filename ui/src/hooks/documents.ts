import { useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { client, unwrap, streamJob, type JobEvent } from "@/lib/api";
import { humanizeError } from "@/lib/errors";
import { PAGE_SIZE } from "@/components/common/Pagination";
import type { DraftIn, GenerateIn, SendIn } from "@/api/types";

type SendBody = SendIn;

export const docKeys = {
  patientDocs: (id: number, page: number) => ["patient-docs", id, page] as const,
  filtered: (f: DocFilter, page: number) => ["documents", f, page] as const,
  genTemplates: (mode: string) => ["gen-templates", mode] as const,
  genForm: (id: number, template: string, docId?: number | null, srcId?: number | null) =>
    ["gen-form", id, template, docId ?? null, srcId ?? null] as const,
};

export type DocFilter = { search: string; statut: string; date_from: string; date_to: string };

function invalidateAfterDoc(qc: ReturnType<typeof useQueryClient>, patientId?: number) {
  qc.invalidateQueries({ queryKey: ["documents"] });
  qc.invalidateQueries({ queryKey: ["patient-docs"] });
  qc.invalidateQueries({ queryKey: ["jobs"] });
  if (patientId != null) {
    qc.invalidateQueries({ queryKey: ["patients"] });
    qc.invalidateQueries({ queryKey: ["clinical", patientId] });
    qc.invalidateQueries({ queryKey: ["audit", patientId] });
  }
}

// --- Lectures ----------------------------------------------------------------

export function usePatientDocuments(id: number | null, page: number) {
  return useQuery({
    enabled: id != null,
    queryKey: docKeys.patientDocs(id ?? 0, page),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/patients/{patient_id}/documents", {
          params: { path: { patient_id: id! }, query: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
        }),
      ),
  });
}

export function useDocumentsFiltered(f: DocFilter, page: number) {
  return useQuery({
    queryKey: docKeys.filtered(f, page),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/documents", {
          params: {
            query: { ...f, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
          },
        }),
      ),
  });
}

export function useGenerationTemplates(mode: string, enabled = true) {
  return useQuery({
    enabled,
    queryKey: docKeys.genTemplates(mode),
    queryFn: async () =>
      unwrap(await client.GET("/api/generation/templates", { params: { query: { mode } } })),
  });
}

export function useGenerationForm(
  id: number | null,
  template: string | null,
  documentId?: number | null,
  sourcePrestationId?: number | null,
) {
  return useQuery({
    enabled: id != null && !!template,
    queryKey: docKeys.genForm(id ?? 0, template ?? "", documentId, sourcePrestationId),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/patients/{patient_id}/generation/form", {
          params: {
            path: { patient_id: id! },
            query: {
              template: template!,
              document_id: documentId ?? undefined,
              source_prestation_id: sourcePrestationId ?? undefined,
            },
          },
        }),
      ),
  });
}

// --- Brouillon (synchrone) ---------------------------------------------------

export function useSaveDraft(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: DraftIn) =>
      unwrap(
        await client.POST("/api/patients/{patient_id}/documents/draft", {
          params: { path: { patient_id: patientId } },
          body,
        }),
      ),
    onSuccess: () => invalidateAfterDoc(qc, patientId),
  });
}

// --- Opérations longues (SSE) ------------------------------------------------

/**
 * Lance la génération côté serveur et renvoie le `job_id` SANS attendre la fin.
 *
 * Le POST est rapide (202 + job_id) : il valide de façon synchrone (ex. imprimante
 * pour « Générer et imprimer ») puis planifie le rendu Word dans le worker sérialisé.
 * Le suivi de l'opération longue est délégué à `useTrackJob` (toast en arrière-plan),
 * pour ne pas bloquer le dialogue ni l'interface. L'invalidation des listes a donc
 * lieu à la FIN du job (dans le tracker), pas au retour du POST (rien n'est encore
 * persisté à ce stade — le brouillon est créé dans la tâche worker).
 */
export function useGenerate(patientId: number) {
  return useMutation({
    mutationFn: async (body: GenerateIn) => {
      const accepted = unwrap(
        await client.POST("/api/patients/{patient_id}/documents/generate", {
          params: { path: { patient_id: patientId } },
          body,
        }),
      );
      return accepted.job_id;
    },
  });
}

/**
 * Suit une opération longue (job SSE) **en arrière-plan**, détaché du composant qui
 * l'a lancée : un toast « … en cours » se promeut en succès/erreur à la fin, et les
 * listes concernées sont rafraîchies. Le streaming et le toast (sonner) sont globaux,
 * donc ils survivent à la fermeture du dialogue — l'utilisateur peut continuer à
 * travailler pendant le rendu Word.
 */
export function useTrackJob() {
  const qc = useQueryClient();
  return useCallback(
    (jobId: string, opts: { loading: string; success: string; patientId?: number }) => {
      const toastId = toast.loading(opts.loading);
      streamJob(jobId, (e) => {
        if (e.type === "progress" && e.message) toast.loading(e.message, { id: toastId });
      })
        .then(() => toast.success(opts.success, { id: toastId }))
        .catch((err) => toast.error(humanizeError(err), { id: toastId }))
        // Rafraîchir même en cas d'erreur : le statut du document a pu passer à « erreur ».
        .finally(() => invalidateAfterDoc(qc, opts.patientId));
    },
    [qc],
  );
}

export function useRenderDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, onEvent }: { id: number; onEvent?: (e: JobEvent) => void }) => {
      const accepted = unwrap(
        await client.POST("/api/documents/{document_id}/render", {
          params: { path: { document_id: id } },
        }),
      );
      await streamJob(accepted.job_id, onEvent ?? (() => {}));
    },
    onSuccess: () => invalidateAfterDoc(qc),
  });
}

export function usePrintDocument() {
  return useMutation({
    mutationFn: async ({ id, onEvent }: { id: number; onEvent?: (e: JobEvent) => void }) => {
      const accepted = unwrap(
        await client.POST("/api/documents/{document_id}/print", {
          params: { path: { document_id: id } },
        }),
      );
      await streamJob(accepted.job_id, onEvent ?? (() => {}));
    },
  });
}

export function useSendDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      body,
      onEvent,
    }: {
      id: number;
      body: SendBody;
      onEvent?: (e: JobEvent) => void;
    }) => {
      const accepted = unwrap(
        await client.POST("/api/documents/{document_id}/send", {
          params: { path: { document_id: id } },
          body,
        }),
      );
      await streamJob(accepted.job_id, onEvent ?? (() => {}));
    },
    onSuccess: () => invalidateAfterDoc(qc),
  });
}

export function useRefreshStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, onEvent }: { id: number; onEvent?: (e: JobEvent) => void }) => {
      const accepted = unwrap(
        await client.POST("/api/documents/{document_id}/refresh-status", {
          params: { path: { document_id: id } },
        }),
      );
      await streamJob(accepted.job_id, onEvent ?? (() => {}));
    },
    onSuccess: () => invalidateAfterDoc(qc),
  });
}

export function useOpenDocument() {
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await client.POST("/api/documents/{document_id}/open", {
          params: { path: { document_id: id } },
        }),
      ),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await client.DELETE("/api/documents/{document_id}", {
          params: { path: { document_id: id } },
        }),
      ),
    onSuccess: () => invalidateAfterDoc(qc),
  });
}
