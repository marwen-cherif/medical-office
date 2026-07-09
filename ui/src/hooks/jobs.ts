import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, streamJob, type JobEvent } from "@/lib/api";
import { PAGE_SIZE } from "@/components/common/Pagination";

export type JobFilter = { date_from: string; date_to: string };

export function useJobs(f: JobFilter, page: number) {
  return useQuery({
    queryKey: ["jobs", f, page],
    queryFn: async () =>
      unwrap(
        await client.GET("/api/jobs", {
          params: { query: { ...f, limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
        }),
      ),
  });
}

export function useJob(id: number | null) {
  return useQuery({
    enabled: id != null,
    queryKey: ["job", id],
    queryFn: async () =>
      unwrap(await client.GET("/api/jobs/{job_id}", { params: { path: { job_id: id! } } })),
  });
}

export function useBatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      kind,
      documentIds,
      mailjetTemplateId,
      onEvent,
    }: {
      kind: "generation" | "envoi";
      documentIds: number[];
      mailjetTemplateId?: number | null;
      onEvent?: (e: JobEvent) => void;
    }) => {
      const accepted = unwrap(
        await client.POST("/api/documents/batch", {
          body: { kind, document_ids: documentIds, mailjet_template_id: mailjetTemplateId ?? null },
        }),
      );
      await streamJob(accepted.job_id, onEvent ?? (() => {}));
      return accepted;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useRelaunchJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, onEvent }: { id: number; onEvent?: (e: JobEvent) => void }) => {
      const accepted = unwrap(
        await client.POST("/api/jobs/{job_id}/relaunch", { params: { path: { job_id: id } } }),
      );
      await streamJob(accepted.job_id, onEvent ?? (() => {}));
      return accepted;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job"] });
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}
