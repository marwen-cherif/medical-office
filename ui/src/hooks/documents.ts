import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, streamJob, type JobEvent } from "@/lib/api";
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

export function useGenerate(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ body, onEvent }: { body: GenerateIn; onEvent?: (e: JobEvent) => void }) => {
      const accepted = unwrap(
        await client.POST("/api/patients/{patient_id}/documents/generate", {
          params: { path: { patient_id: patientId } },
          body,
        }),
      );
      await streamJob(accepted.job_id, onEvent ?? (() => {}));
    },
    onSuccess: () => invalidateAfterDoc(qc, patientId),
  });
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
