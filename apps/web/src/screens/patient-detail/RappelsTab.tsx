/**
 * Onglet « Rappels » de la fiche patient.
 *
 * Liste les rappels rattachés à ce patient avec actions rapides :
 * modifier, ignorer, envoyer WhatsApp, traiter, annuler.
 *
 * La création d'un rappel se fait via le bouton flottant de la fiche patient
 * (FAB en bas à droite, raccourci Alt+P) — pas de bouton ici pour éviter le
 * doublon. Le dialog reste pour l'édition des rappels existants.
 */
import { useState } from 'react';
import { Bell, MessageSquare } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { humanizeError } from '@/lib/errors';
import { isoToFr } from '@/lib/format';
import { rappelEtatBadge, rappelTypeLabel } from '@/lib/rappels';
import {
  useRappels,
  useIgnorerRappel,
  useMarquerEnvoye,
  useMarquerTraite,
  useAnnulerRappel,
  useWhatsAppLink,
} from '@/hooks/rappels';
import { RappelFormDialog } from '@/screens/rappels/RappelFormDialog';
import type { Rappel } from '@/api/types';

interface Props {
  patientId: number;
}

export function RappelsTab({ patientId }: Props) {
  const [formTarget, setFormTarget] = useState<Rappel | 'new' | null>(null);

  const { data, isLoading, isError, error } = useRappels(undefined, patientId);
  const items = data?.items ?? [];

  const ignorer = useIgnorerRappel();
  const envoye = useMarquerEnvoye();
  const traite = useMarquerTraite();
  const annuler = useAnnulerRappel();
  const waLink = useWhatsAppLink();

  function handleSend(r: Rappel) {
    waLink.mutate(
      { id: r.id },
      {
        onSuccess: (res) => {
          window.open(res.url, '_blank', 'noopener,noreferrer');
          envoye.mutate(r.id, {
            onError: (e) => toast.error(humanizeError(e)),
          });
        },
        onError: (e) => toast.error(humanizeError(e)),
      }
    );
  }

  if (isLoading) return <p className="py-8 text-center text-muted">Chargement…</p>;
  if (isError) return <p className="py-8 text-center text-red">{humanizeError(error)}</p>;

  return (
    <div className="space-y-3">
      {/* Liste */}
      {items.length === 0 ? (
        <div className="rounded-[var(--radius)] border border-line bg-white py-12 text-center text-muted text-sm">
          Aucun rappel pour ce patient.
        </div>
      ) : (
        <div className="rounded-[var(--radius)] border border-line bg-white divide-y divide-line">
          {items.map((r) => {
            const { label: etatLabel, variant: etatVariant } = rappelEtatBadge(r.etat);
            const canEdit = !['envoye', 'traite', 'annule'].includes(r.etat);
            const isOverdue = r.etat === 'planifie' && new Date(r.echeance) < new Date();

            return (
              <div key={r.id} className="flex items-start gap-3 px-4 py-3">
                {/* Icône */}
                <div className="mt-0.5 shrink-0">
                  {r.type === 'message_patient' ? (
                    <MessageSquare className="size-4 text-emerald-500" />
                  ) : (
                    <Bell className="size-4 text-amber-500" />
                  )}
                </div>

                {/* Infos */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-sm text-ink truncate">{r.titre}</span>
                    <Badge variant={etatVariant}>{etatLabel}</Badge>
                  </div>
                  <div className="mt-0.5 text-xs text-muted">
                    {rappelTypeLabel(r.type)} ·{' '}
                    <span className={isOverdue ? 'text-red font-semibold' : ''}>
                      {isoToFr(r.echeance.slice(0, 10))}
                    </span>
                  </div>
                  {r.message && (
                    <p className="mt-1 text-xs text-muted line-clamp-2 italic">"{r.message}"</p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex shrink-0 items-center gap-1">
                  {canEdit && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => setFormTarget(r)}
                    >
                      Modifier
                    </Button>
                  )}
                  {['du', 'a_envoyer'].includes(r.etat) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() =>
                        ignorer.mutate(r.id, { onError: (e) => toast.error(humanizeError(e)) })
                      }
                    >
                      Ignorer
                    </Button>
                  )}
                  {r.etat === 'a_envoyer' && (
                    <Button
                      size="sm"
                      className="h-7 px-2 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                      onClick={() => handleSend(r)}
                    >
                      <MessageSquare className="size-3 mr-1" /> Envoyer
                    </Button>
                  )}
                  {['du', 'a_envoyer'].includes(r.etat) && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() =>
                        traite.mutate(r.id, { onError: (e) => toast.error(humanizeError(e)) })
                      }
                    >
                      Traité
                    </Button>
                  )}
                  {r.etat === 'planifie' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs text-red hover:text-red"
                      onClick={() =>
                        annuler.mutate(r.id, {
                          onSuccess: () => toast.success('Rappel annulé.'),
                          onError: (e) => toast.error(humanizeError(e)),
                        })
                      }
                    >
                      Annuler
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Dialog création/édition pré-rempli avec le patient */}
      <RappelFormDialog
        target={formTarget}
        onClose={() => setFormTarget(null)}
        defaultPatientId={patientId}
      />
    </div>
  );
}
