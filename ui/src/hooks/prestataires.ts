import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap } from "@/lib/api";
import { backend } from "@/lib/bridge";
import { PAGE_SIZE } from "@/components/common/Pagination";
import type { DepenseIn, PrestataireIn, ReglementDepenseIn } from "@/api/types";

export const prKeys = {
  list: (search: string, page: number) => ["prestataires", { search, page }] as const,
  detail: (id: number) => ["prestataires", id] as const,
  factures: (id: number, page: number) => ["factures", id, page] as const,
  depenses: (id: number, page: number) => ["pr-depenses", id, page] as const,
};

function invalidate(qc: ReturnType<typeof useQueryClient>, id?: number) {
  qc.invalidateQueries({ queryKey: ["prestataires"] });
  qc.invalidateQueries({ queryKey: ["fin-depenses"] });
  if (id != null) {
    qc.invalidateQueries({ queryKey: ["factures", id] });
    qc.invalidateQueries({ queryKey: ["pr-depenses", id] });
  }
}

export function usePrestataires(search: string, page: number) {
  return useQuery({
    queryKey: prKeys.list(search, page),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/prestataires", {
          params: { query: { search, limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
        }),
      ),
  });
}

/** Tous les prestataires (pour un sélecteur recherchable, sans pagination). */
export function useAllPrestataires() {
  return useQuery({
    queryKey: ["prestataires", "all"],
    queryFn: async () =>
      unwrap(
        await client.GET("/api/prestataires", {
          params: { query: { search: "", limit: 1000, offset: 0 } },
        }),
      ),
  });
}

export function usePrestataire(id: number | null) {
  return useQuery({
    enabled: id != null,
    queryKey: prKeys.detail(id ?? 0),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/prestataires/{prestataire_id}", {
          params: { path: { prestataire_id: id! } },
        }),
      ),
  });
}

export function useCreatePrestataire() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PrestataireIn) =>
      unwrap(await client.POST("/api/prestataires", { body })),
    onSuccess: () => invalidate(qc),
  });
}

export function useUpdatePrestataire() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: PrestataireIn }) =>
      unwrap(
        await client.PUT("/api/prestataires/{prestataire_id}", {
          params: { path: { prestataire_id: id } },
          body,
        }),
      ),
    onSuccess: (_d, v) => invalidate(qc, v.id),
  });
}

export function useFactures(id: number | null, page: number) {
  return useQuery({
    enabled: id != null,
    queryKey: prKeys.factures(id ?? 0, page),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/prestataires/{prestataire_id}/factures", {
          params: { path: { prestataire_id: id! }, query: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
        }),
      ),
  });
}

export function useProviderDepenses(id: number | null, page: number) {
  return useQuery({
    enabled: id != null,
    queryKey: prKeys.depenses(id ?? 0, page),
    queryFn: async () =>
      unwrap(
        await client.GET("/api/prestataires/{prestataire_id}/depenses", {
          params: { path: { prestataire_id: id! }, query: { limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
        }),
      ),
  });
}

/** Import (upload multipart) d'une facture — fetch direct (openapi-fetch + FormData). */
export function useImportFacture(prestataireId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, montant, libelle }: { file: File; montant?: number; libelle?: string }) => {
      const fd = new FormData();
      fd.append("file", file);
      if (montant != null) fd.append("montant", String(montant));
      if (libelle) fd.append("libelle", libelle);
      const resp = await fetch(
        `${backend.baseUrl}/api/prestataires/${prestataireId}/factures`,
        { method: "POST", headers: { Authorization: `Bearer ${backend.token}` }, body: fd },
      );
      if (!resp.ok) throw await resp.json();
      return resp.json();
    },
    onSuccess: () => invalidate(qc, prestataireId),
  });
}

/** Extraction IA configurée ? (config.ini — stable au runtime, mis en cache). */
export function useFactureIaDisponible() {
  return useQuery({
    queryKey: ["facture-ia-disponible"],
    staleTime: Infinity,
    queryFn: async () => unwrap(await client.GET("/api/factures/ia-disponible")),
  });
}

/** Lit le montant TTC d'une facture par IA (pré-remplissage éditable). Ne crée rien. */
export function useExtractFactureMontant() {
  return useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const resp = await fetch(`${backend.baseUrl}/api/factures/ia-montant`, {
        method: "POST",
        headers: { Authorization: `Bearer ${backend.token}` },
        body: fd,
      });
      if (!resp.ok) throw await resp.json();
      return resp.json() as Promise<{ disponible: boolean; montant: number | null }>;
    },
  });
}

export function useDeleteFacture(prestataireId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(await client.DELETE("/api/factures/{facture_id}", { params: { path: { facture_id: id } } })),
    onSuccess: () => invalidate(qc, prestataireId),
  });
}

export function useCreateDepense() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: DepenseIn) => unwrap(await client.POST("/api/depenses", { body })),
    onSuccess: (_d, v) => invalidate(qc, v.prestataire_id),
  });
}

export function useRegleDepense(prestataireId?: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: ReglementDepenseIn }) =>
      unwrap(
        await client.POST("/api/depenses/{depense_id}/reglement", {
          params: { path: { depense_id: id } },
          body,
        }),
      ),
    onSuccess: () => invalidate(qc, prestataireId),
  });
}

export function useDeleteDepense(prestataireId?: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(await client.DELETE("/api/depenses/{depense_id}", { params: { path: { depense_id: id } } })),
    onSuccess: () => invalidate(qc, prestataireId),
  });
}
