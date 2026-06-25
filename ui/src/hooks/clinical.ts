import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap } from "@/lib/api";
import { PAGE_SIZE } from "@/components/common/Pagination";
import type { CascadeIn, PaiementIn, PlanIn, PrestationIn, ReglementIn } from "@/api/types";

export const clinicalKeys = {
  clinical: (id: number) => ["clinical", id] as const,
  encaissements: (id: number, page: number) => ["encaissements", id, page] as const,
  creances: (id: number, notes: boolean) => ["creances", id, notes] as const,
  audit: (id: number) => ["audit", id] as const,
};

/** Invalide tout ce qui dépend du solde/actes d'un patient après une mutation. */
function invalidatePatient(qc: ReturnType<typeof useQueryClient>, id: number) {
  qc.invalidateQueries({ queryKey: ["patients"] });
  qc.invalidateQueries({ queryKey: ["clinical", id] });
  qc.invalidateQueries({ queryKey: ["encaissements", id] });
  qc.invalidateQueries({ queryKey: ["creances", id] });
  qc.invalidateQueries({ queryKey: ["audit", id] });
}

// --- Lectures ----------------------------------------------------------------

export function useClinical(id: number | null) {
  return useQuery({
    enabled: id != null,
    queryKey: clinicalKeys.clinical(id ?? 0),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/patients/{patient_id}/clinical", {
          params: { path: { patient_id: id! } },
        }),
      ),
  });
}

export function useEncaissements(id: number | null, page: number) {
  return useQuery({
    enabled: id != null,
    queryKey: clinicalKeys.encaissements(id ?? 0, page),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/patients/{patient_id}/encaissements", {
          params: { path: { patient_id: id! }, query: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
        }),
      ),
  });
}

export function useCreances(id: number | null, includeNotes: boolean) {
  return useQuery({
    enabled: id != null,
    queryKey: clinicalKeys.creances(id ?? 0, includeNotes),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/patients/{patient_id}/creances", {
          params: { path: { patient_id: id! }, query: { include_notes: includeNotes } },
        }),
      ),
  });
}

export function useAudit(id: number | null) {
  return useQuery({
    enabled: id != null,
    queryKey: clinicalKeys.audit(id ?? 0),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/patients/{patient_id}/audit", {
          params: { path: { patient_id: id! }, query: { limit: 200 } },
        }),
      ),
  });
}

// --- Plans -------------------------------------------------------------------

export function useCreatePlan(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PlanIn) =>
      unwrap(
        await client.POST("/api/patients/{patient_id}/plans", {
          params: { path: { patient_id: patientId } },
          body,
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

export function useUpdatePlan(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ planId, body }: { planId: number; body: PlanIn }) =>
      unwrap(
        await client.PUT("/api/plans/{plan_id}", {
          params: { path: { plan_id: planId } },
          body,
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

export function useDeletePlan(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (planId: number) =>
      unwrap(await client.DELETE("/api/plans/{plan_id}", { params: { path: { plan_id: planId } } })),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

// --- Prestations (actes réalisés) --------------------------------------------

export function useCreatePrestation(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PrestationIn) =>
      unwrap(
        await client.POST("/api/patients/{patient_id}/prestations", {
          params: { path: { patient_id: patientId } },
          body,
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

export function useUpdatePrestation(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: PrestationIn }) =>
      unwrap(
        await client.PUT("/api/prestations/{prestation_id}", {
          params: { path: { prestation_id: id } },
          body,
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

export function useDeletePrestation(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await client.DELETE("/api/prestations/{prestation_id}", {
          params: { path: { prestation_id: id } },
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

export function usePrestationReglement(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: ReglementIn }) =>
      unwrap(
        await client.POST("/api/prestations/{prestation_id}/reglement", {
          params: { path: { prestation_id: id } },
          body,
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

export function useCascadeRegler(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: CascadeIn) =>
      unwrap(
        await client.POST("/api/patients/{patient_id}/regler", {
          params: { path: { patient_id: patientId } },
          body,
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

// --- Notes / paiements -------------------------------------------------------

export function useCreatePaiement(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PaiementIn) =>
      unwrap(
        await client.POST("/api/patients/{patient_id}/paiements", {
          params: { path: { patient_id: patientId } },
          body,
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

/** Règlement (partiel ou total) d'une note, comme pour un acte. */
export function usePaiementReglement(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: ReglementIn }) =>
      unwrap(
        await client.POST("/api/paiements/{paiement_id}/reglement", {
          params: { path: { paiement_id: id } },
          body,
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

export function useEncaisserPaiement(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, mode, date }: { id: number; mode?: string; date?: string }) =>
      unwrap(
        await client.POST("/api/paiements/{paiement_id}/encaisser", {
          params: { path: { paiement_id: id } },
          body: { mode: mode ?? null, date_encaissement: date ?? null },
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}

export function useDeletePaiement(patientId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await client.DELETE("/api/paiements/{paiement_id}", {
          params: { path: { paiement_id: id } },
        }),
      ),
    onSuccess: () => invalidatePatient(qc, patientId),
  });
}
