import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap } from "@/lib/api";
import { PAGE_SIZE } from "@/components/common/Pagination";

export type FinFilter = { statut: string; search: string; date_from: string; date_to: string };

export function useFinancePaiements(f: FinFilter, page: number) {
  return useQuery({
    queryKey: ["fin-paiements", f, page],
    queryFn: async () =>
      unwrap(
        await client.GET("/api/finances/paiements", {
          params: { query: { ...f, limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
        }),
      ),
  });
}

export function useFinanceDepenses(f: FinFilter, page: number) {
  return useQuery({
    queryKey: ["fin-depenses", f, page],
    queryFn: async () =>
      unwrap(
        await client.GET("/api/finances/depenses", {
          params: { query: { ...f, limit: PAGE_SIZE, offset: page * PAGE_SIZE } },
        }),
      ),
  });
}

function invalidateFin(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["fin-paiements"] });
  qc.invalidateQueries({ queryKey: ["patients"] });
  qc.invalidateQueries({ queryKey: ["clinical"] });
}

/** Marque une note (paiement) encaissée depuis l'écran Finances. */
export function useEncaisserNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, mode, date }: { id: number; mode?: string; date?: string }) =>
      unwrap(
        await client.POST("/api/paiements/{paiement_id}/encaisser", {
          params: { path: { paiement_id: id } },
          body: { mode: mode ?? null, date_encaissement: date ?? null },
        }),
      ),
    onSuccess: () => invalidateFin(qc),
  });
}

/** Annule (supprime) une note en attente depuis l'écran Finances. */
export function useAnnulerNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) =>
      unwrap(
        await client.DELETE("/api/paiements/{paiement_id}", {
          params: { path: { paiement_id: id } },
        }),
      ),
    onSuccess: () => invalidateFin(qc),
  });
}
