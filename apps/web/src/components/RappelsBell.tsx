/**
 * Cloche de notifications Rappels dans la barre latérale.
 *
 * - Badge numérique (rappels actifs non lus : état `du` ou `a_envoyer`, `lu=false`).
 * - Clic → popover avec la liste des rappels actifs et les actions rapides.
 * - Rafraîchissement automatique toutes les 60 s (géré dans useRappelsCountActifs).
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Bell, MessageSquare, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tooltip } from '@/components/common/Tooltip';
import { WhatsAppIcon } from '@/components/icons/WhatsAppIcon';
import { humanizeError } from '@/lib/errors';
import { isoToFr } from '@/lib/format';
import {
  useRappelsCountActifs,
  useRappels,
  useIgnorerRappel,
  useWhatsAppLink,
  useMarquerEnvoye,
  rappelKeys,
} from '@/hooks/rappels';
import type { Rappel } from '@/api/types';

export function RappelsBell() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const countQ = useRappelsCountActifs();
  const count = countQ.data?.count ?? 0;

  // Rafraîchit le badge quand la fenêtre redevient active (la cloche est montée
  // en permanence dans le Shell). Satisfait « Rafraîchissement si l'app est déjà
  // ouverte à l'échéance » sans activer refetchOnWindowFocus pour tout le monde.
  useEffect(() => {
    const refresh = () => qc.invalidateQueries({ queryKey: rappelKeys.countActifs });
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [qc]);

  // Charge les rappels actifs seulement quand le popover est ouvert.
  const listQ = useRappels(open ? 'du,a_envoyer' : undefined);
  const actifs = open ? (listQ.data?.items ?? []) : [];

  const ignorer = useIgnorerRappel();
  const waLink = useWhatsAppLink();
  const envoye = useMarquerEnvoye();

  function handleSend(r: Rappel) {
    waLink.mutate(
      { id: r.id },
      {
        onSuccess: (res) => {
          window.open(res.url, '_blank', 'noopener,noreferrer');
          envoye.mutate(r.id, {
            onError: (e) => toast.error(humanizeError(e)),
          });
          setOpen(false);
        },
        onError: (e) => toast.error(humanizeError(e)),
      }
    );
  }

  function handleIgnorer(r: Rappel) {
    ignorer.mutate(r.id, {
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="relative flex items-center gap-3 rounded-[var(--radius)] px-3 py-2 text-sm font-medium text-ink transition-colors hover:bg-bg w-full"
          title="Rappels"
        >
          <Bell className="size-4 shrink-0" />
          <span className="flex-1 text-left">Rappels</span>
          {count > 0 && (
            <span className="flex size-5 items-center justify-center rounded-full bg-red text-[10px] font-bold text-white leading-none">
              {count > 99 ? '99+' : count}
            </span>
          )}
        </button>
      </PopoverTrigger>

      <PopoverContent side="right" align="end" sideOffset={8} className="w-80 p-0 overflow-hidden">
        {/* En-tête */}
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <span className="text-sm font-semibold text-ink">Rappels actifs</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => {
              setOpen(false);
              navigate('/rappels');
            }}
          >
            Voir tous <ExternalLink className="ml-1 size-3" />
          </Button>
        </div>

        {/* Contenu */}
        <div className="max-h-96 overflow-y-auto">
          {listQ.isLoading && (
            <p className="px-4 py-6 text-center text-sm text-muted">Chargement…</p>
          )}
          {!listQ.isLoading && actifs.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-muted">Aucun rappel en attente. ✓</p>
          )}
          {actifs.map((r) => (
            <div
              key={r.id}
              role="button"
              tabIndex={0}
              onClick={() => handleIgnorer(r)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleIgnorer(r);
                }
              }}
              className="border-b border-line px-4 py-3 last:border-0 cursor-pointer transition-colors hover:bg-bg"
              title="Cliquer pour ignorer ce rappel"
            >
              <div className="flex items-start gap-2">
                {r.type === 'message_patient' ? (
                  <MessageSquare className="mt-0.5 size-3.5 shrink-0 text-emerald-500" />
                ) : (
                  <Bell className="mt-0.5 size-3.5 shrink-0 text-amber-500" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="truncate text-sm font-medium text-ink">{r.titre}</div>
                  <div className="text-xs text-muted">
                    Échéance : {isoToFr(r.echeance.slice(0, 10))}
                    {r.patient_display && (
                      <>
                        {' · '}
                        <button
                          type="button"
                          className="font-medium text-navy hover:underline"
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpen(false);
                            navigate(`/patients/${r.patient_id}`);
                          }}
                        >
                          {r.patient_display}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Actions — stopPropagation pour ne pas déclencher l'ignore de la ligne */}
              <div className="mt-2 flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => handleIgnorer(r)}
                >
                  Ignorer
                </Button>
                {r.etat === 'a_envoyer' && (
                  <Tooltip label="Envoyer sur WhatsApp">
                    <button
                      type="button"
                      onClick={() => handleSend(r)}
                      className="inline-flex size-7 items-center justify-center rounded-md bg-emerald-600 text-white transition-colors hover:bg-emerald-700"
                    >
                      <WhatsAppIcon className="size-3.5" />
                    </button>
                  </Tooltip>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Pied */}
        {count > 0 && (
          <div className="border-t border-line px-4 py-2 text-right">
            <Badge variant="default">{count} en attente</Badge>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
