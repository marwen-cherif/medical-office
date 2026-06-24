import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap } from "@/lib/api";
import { PAGE_SIZE } from "@/components/common/Pagination";
import type { PatientIn } from "@/api/types";

export const patientKeys = {
  list: (search: string, filtre: string, page: number) =>
    ["patients", { search, filtre, page }] as const,
  detail: (id: number) => ["patients", id] as const,
};

export function usePatients(search: string, filtre: string, page: number) {
  return useQuery({
    queryKey: patientKeys.list(search, filtre, page),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/patients", {
          params: { query: { search, filtre, limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
        }),
      ),
  });
}

export function usePatient(id: number | null) {
  return useQuery({
    enabled: id != null,
    queryKey: patientKeys.detail(id ?? 0),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/patients/{patient_id}", {
          params: { path: { patient_id: id! } },
        }),
      ),
  });
}

export function useCreatePatient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PatientIn) =>
      unwrap(await client.POST("/api/patients", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["patients"] }),
  });
}

export function useUpdatePatient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: PatientIn }) =>
      unwrap(
        await client.PUT("/api/patients/{patient_id}", {
          params: { path: { patient_id: id } },
          body,
        }),
      ),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ["patients"] });
      qc.invalidateQueries({ queryKey: patientKeys.detail(v.id) });
    },
  });
}
