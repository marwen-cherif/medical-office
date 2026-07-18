/**
 * Hooks TanStack Query pour les rappels automatiques.
 *
 * API backend : /api/rappels + /api/settings/rappels
 * Tous les appels passent par `client` (openapi-fetch typé) ou fetch direct pour
 * les routes non encore générées dans schema.d.ts.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { backend } from '@/lib/bridge';
import type {
  Rappel,
  RappelIn,
  RappelList,
  RappelCountActifs,
  RappelProcessDus,
  WhatsAppLinkOut,
  RappelsSettingsOut,
  RappelsSettingsIn,
} from '@/api/types';

// ---------------------------------------------------------------------------
// Helpers fetch direct (les routes rappels ne sont pas encore dans schema.d.ts)
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const resp = await fetch(`${backend.baseUrl}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${backend.token}`,
      ...(options.headers ?? {}),
    },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw body;
  }
  return resp.json() as Promise<T>;
}

/**
 * Marque une liste de rappels comme ignorés (lu/traité) — action « j'ai vu »
 * depuis le toast résumé. Best-effort : ignore les erreurs individuelles.
 * Renvoie le nombre de rappels effectivement ignorés.
 */
export async function ignoreRappelIds(ids: number[]): Promise<number> {
  let done = 0;
  await Promise.all(
    ids.map((id) =>
      apiFetch<Rappel>(`/api/rappels/${id}/ignorer`, { method: 'PATCH' })
        .then(() => {
          done += 1;
        })
        .catch(() => {
          /* best-effort : un échec n'empêche pas les autres */
        })
    )
  );
  return done;
}

// ---------------------------------------------------------------------------
// Clés de cache
// ---------------------------------------------------------------------------

export const rappelKeys = {
  all: ['rappels'] as const,
  list: (etats?: string, patientId?: number) => ['rappels', 'list', { etats, patientId }] as const,
  detail: (id: number) => ['rappels', id] as const,
  countActifs: ['rappels', 'count-actifs'] as const,
  settings: ['settings', 'rappels'] as const,
};

// ---------------------------------------------------------------------------
// Lectures
// ---------------------------------------------------------------------------

export function useRappels(etats?: string, patientId?: number, limit = 200) {
  return useQuery({
    queryKey: rappelKeys.list(etats, patientId),
    queryFn: () => {
      const params = new URLSearchParams();
      if (etats) params.set('etat', etats);
      if (patientId != null) params.set('patient_id', String(patientId));
      params.set('limit', String(limit));
      return apiFetch<RappelList>(`/api/rappels?${params}`);
    },
  });
}

export function useRappel(id: number | null) {
  return useQuery({
    enabled: id != null,
    queryKey: rappelKeys.detail(id ?? 0),
    queryFn: () => apiFetch<Rappel>(`/api/rappels/${id}`),
  });
}

export function useRappelsCountActifs() {
  return useQuery({
    queryKey: rappelKeys.countActifs,
    queryFn: () => apiFetch<RappelCountActifs>('/api/rappels/count-actifs'),
    // Rafraîchi toutes les 60 s pour maintenir le badge à jour sans polling agressif.
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
}

/**
 * Filet de sécurité au démarrage : traite les rappels échus côté backend,
 * rafraîchit le badge, et affiche un toast résumé si des rappels sont en attente.
 *
 * Doit être appelé une seule fois (au montage de l'app). Idempotent côté
 * backend (seuls les rappels `planifie` échus sont traités).
 *
 * `onShow` reçoit le nombre ET les IDs des rappels actifs (pour permettre une
 * action « ignorer » groupée depuis le toast).
 */
export function useRappelsStartup(
  onShow?: (count: number, ids: number[]) => void
) {
  const qc = useQueryClient();
  const notifiedRef = useRef(false);
  useEffect(() => {
    if (notifiedRef.current) return;
    notifiedRef.current = true;
    let mounted = true;
    (async () => {
      try {
        // 1. Traite les rappels dus (planifie → du/a_envoyer).
        await apiFetch<RappelProcessDus>('/api/rappels/process-dus', {
          method: 'POST',
        });
        // 2. Récupère le compte à jour et rafraîchit le badge.
        const { count } = await apiFetch<RappelCountActifs>(
          '/api/rappels/count-actifs'
        );
        qc.invalidateQueries({ queryKey: rappelKeys.countActifs });
        // 3. Si des rappels sont actifs, récupère leurs IDs pour le callback.
        let ids: number[] = [];
        if (count > 0) {
          const list = await apiFetch<RappelList>('/api/rappels?etat=du,a_envoyer');
          ids = (list.items ?? []).map((r) => r.id);
        }
        if (mounted && count > 0 && onShow) onShow(count, ids);
      } catch {
        // Best-effort : ne casse pas le démarrage si le backend n'est pas prêt.
      }
    })();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

export function useRappelsSettings() {
  return useQuery({
    queryKey: rappelKeys.settings,
    queryFn: () => apiFetch<RappelsSettingsOut>('/api/settings/rappels'),
  });
}

// ---------------------------------------------------------------------------
// Mutations CRUD
// ---------------------------------------------------------------------------

export function useCreateRappel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RappelIn) =>
      apiFetch<Rappel>('/api/rappels', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: rappelKeys.all });
      qc.invalidateQueries({ queryKey: rappelKeys.countActifs });
    },
  });
}

export function useUpdateRappel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: RappelIn }) =>
      apiFetch<Rappel>(`/api/rappels/${id}`, {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: rappelKeys.all });
      qc.invalidateQueries({ queryKey: rappelKeys.detail(v.id) });
    },
  });
}

// ---------------------------------------------------------------------------
// Mutations d'état
// ---------------------------------------------------------------------------

function useRappelPatch(action: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Rappel>(`/api/rappels/${id}/${action}`, { method: 'PATCH' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: rappelKeys.all });
      qc.invalidateQueries({ queryKey: rappelKeys.countActifs });
    },
  });
}

/** Ignorer depuis la cloche (alerte → traité, message → lu). */
export function useIgnorerRappel() {
  return useRappelPatch('ignorer');
}

/** Marquer envoyé (après ouverture wa.me). */
export function useMarquerEnvoye() {
  return useRappelPatch('envoye');
}

/** Marquer traité manuellement. */
export function useMarquerTraite() {
  return useRappelPatch('traite');
}

/** Annuler un rappel planifié. */
export function useAnnulerRappel() {
  return useRappelPatch('annuler');
}

// ---------------------------------------------------------------------------
// Lien WhatsApp
// ---------------------------------------------------------------------------

export function useWhatsAppLink() {
  return useMutation({
    mutationFn: ({ id, phoneId }: { id: number; phoneId?: number }) => {
      const params = phoneId != null ? `?phone_id=${phoneId}` : '';
      return apiFetch<WhatsAppLinkOut>(`/api/rappels/${id}/whatsapp-link${params}`);
    },
  });
}

// ---------------------------------------------------------------------------
// Paramètres rappels
// ---------------------------------------------------------------------------

export function useSetRappelsSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RappelsSettingsIn) =>
      apiFetch<{ ok: boolean }>('/api/settings/rappels', {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: rappelKeys.settings }),
  });
}

export function useInstallRappelsTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<RappelsSettingsOut>('/api/settings/rappels/install-task', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: rappelKeys.settings }),
  });
}

export function useTestRappelsNotification() {
  return useMutation({
    mutationFn: () =>
      apiFetch<{ ok: boolean }>('/api/settings/rappels/test-notification', {
        method: 'POST',
      }),
  });
}
