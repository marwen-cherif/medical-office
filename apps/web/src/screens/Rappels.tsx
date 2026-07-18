/**
 * Écran principal « Rappels » — liste filtrable + actions.
 *
 * Filtres : tous / planifiés / dus / à envoyer / envoyés / traités / annulés
 * Actions par ligne :
 *   - Modifier  (si planifié/dû/à_envoyer)
 *   - Ignorer   (marquer lu/traité depuis la liste)
 *   - Envoyer WhatsApp + marquer envoyé (si message_patient)
 *   - Marquer traité
 *   - Annuler
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, MessageSquare, Plus, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { WhatsAppIcon } from '@/components/icons/WhatsAppIcon';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { humanizeError } from '@/lib/errors';
import { isoToFr, isoToFrDateTime } from '@/lib/format';
import {
  useRappels,
  useIgnorerRappel,
  useMarquerEnvoye,
  useMarquerTraite,
  useAnnulerRappel,
  useWhatsAppLink,
} from '@/hooks/rappels';
import { RappelFormDialog } from './rappels/RappelFormDialog';
import { rappelEtatBadge, rappelTypeLabel } from '@/lib/rappels';
import type { Rappel } from '@/api/types';

// ---------------------------------------------------------------------------
// Filtres d'état
// ---------------------------------------------------------------------------
const FILTRES = [
  { value: '', label: 'Tous' },
  { value: 'planifie', label: 'Planifiés' },
  { value: 'du,a_envoyer', label: 'À traiter' },
  { value: 'a_envoyer', label: 'File WhatsApp' },
  { value: 'envoye,traite', label: 'Traités' },
  { value: 'annule', label: 'Annulés' },
];

// ---------------------------------------------------------------------------
// Composant principal
// ---------------------------------------------------------------------------
export function Rappels() {
  const [filtreEtat, setFiltreEtat] = useState('');
  const [formTarget, setFormTarget] = useState<Rappel | 'new' | null>(null);

  const { data, isLoading, isError, error, refetch } = useRappels(filtreEtat || undefined);
  const ignorer = useIgnorerRappel();
  const envoye = useMarquerEnvoye();
  const traite = useMarquerTraite();
  const annuler = useAnnulerRappel();
  const waLink = useWhatsAppLink();

  const items = data?.items ?? [];

  function handleSendWhatsApp(r: Rappel) {
    waLink.mutate(
      { id: r.id },
      {
        onSuccess: (res) => {
          window.open(res.url, '_blank', 'noopener,noreferrer');
          // Marquer envoyé après ouverture du lien
          envoye.mutate(r.id, {
            onError: (e) => toast.error(humanizeError(e)),
          });
        },
        onError: (e) => toast.error(humanizeError(e)),
      }
    );
  }

  const canEdit = (r: Rappel) => !['envoye', 'traite', 'annule'].includes(r.etat);

  return (
    <div className="mx-auto max-w-5xl p-8">
      {/* En-tête */}
      <header className="mb-6 flex items-center gap-4">
        <div className="flex-1">
          <h1 className="text-2xl font-semibold text-ink">Rappels</h1>
          <p className="mt-1 text-sm text-muted">
            Alertes internes et messages patients WhatsApp planifiés.
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={() => refetch()} title="Actualiser">
          <RefreshCw className="size-4" />
        </Button>
        <Button onClick={() => setFormTarget('new')}>
          <Plus className="size-4" /> Nouveau rappel
        </Button>
      </header>

      {/* Filtres */}
      <div className="mb-4 flex flex-wrap gap-2">
        {FILTRES.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFiltreEtat(f.value)}
            className={[
              'rounded-full border px-3 py-1 text-sm font-medium transition-colors',
              filtreEtat === f.value
                ? 'border-navy bg-navy text-white'
                : 'border-line bg-white text-ink hover:bg-bg',
            ].join(' ')}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* États de chargement */}
      {isLoading && <p className="py-12 text-center text-muted">Chargement…</p>}
      {isError && <p className="py-12 text-center text-red">{humanizeError(error)}</p>}

      {/* Table */}
      {!isLoading && !isError && (
        <>
          {items.length === 0 ? (
            <div className="rounded-[var(--radius)] border border-line bg-white py-16 text-center text-muted">
              Aucun rappel{filtreEtat ? ' pour ce filtre' : ''}.
            </div>
          ) : (
            <div className="rounded-[var(--radius)] border border-line bg-white overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8"></TableHead>
                    <TableHead>Titre</TableHead>
                    <TableHead>Échéance</TableHead>
                    <TableHead>État</TableHead>
                    <TableHead>Patient</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((r) => (
                    <RappelRow
                      key={r.id}
                      rappel={r}
                      canEdit={canEdit(r)}
                      onEdit={() => setFormTarget(r)}
                      onIgnorer={() =>
                        ignorer.mutate(r.id, {
                          onError: (e) => toast.error(humanizeError(e)),
                        })
                      }
                      onSendWhatsApp={() => handleSendWhatsApp(r)}
                      onTraite={() =>
                        traite.mutate(r.id, {
                          onError: (e) => toast.error(humanizeError(e)),
                        })
                      }
                      onAnnuler={() =>
                        annuler.mutate(r.id, {
                          onSuccess: () => toast.success('Rappel annulé.'),
                          onError: (e) => toast.error(humanizeError(e)),
                        })
                      }
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          <p className="mt-2 text-right text-xs text-muted">
            {data?.total ?? 0} rappel{(data?.total ?? 0) !== 1 ? 's' : ''}
          </p>
        </>
      )}

      <RappelFormDialog target={formTarget} onClose={() => setFormTarget(null)} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ligne de table
// ---------------------------------------------------------------------------
interface RowProps {
  rappel: Rappel;
  canEdit: boolean;
  onEdit: () => void;
  onIgnorer: () => void;
  onSendWhatsApp: () => void;
  onTraite: () => void;
  onAnnuler: () => void;
}

function RappelRow({
  rappel: r,
  canEdit,
  onEdit,
  onIgnorer,
  onSendWhatsApp,
  onTraite,
  onAnnuler,
}: RowProps) {
  const { label: etatLabel, variant: etatVariant } = rappelEtatBadge(r.etat);
  const isOverdue = r.etat === 'planifie' && new Date(r.echeance) < new Date();

  return (
    <TableRow
      className={r.lu === false && ['du', 'a_envoyer'].includes(r.etat) ? 'font-medium' : ''}
    >
      {/* Icône type */}
      <TableCell className="px-3 text-muted">
        {r.type === 'message_patient' ? (
          <MessageSquare className="size-3.5 text-emerald-500" />
        ) : (
          <Bell className="size-3.5 text-amber-500" />
        )}
      </TableCell>

      {/* Titre + description */}
      <TableCell>
        <div>{r.titre}</div>
        {r.message && <div className="text-xs text-muted line-clamp-1 italic">{r.message}</div>}
        {!r.message && <div className="text-xs text-muted">{rappelTypeLabel(r.type)}</div>}
      </TableCell>

      {/* Échéance */}
      <TableCell>
        <span className={isOverdue ? 'text-red font-semibold' : ''}>
          {isoToFr(r.echeance.slice(0, 10))}
        </span>
        {r.echeance.length > 10 && (
          <div className="text-xs text-muted">{isoToFrDateTime(r.echeance)}</div>
        )}
      </TableCell>

      {/* État */}
      <TableCell>
        <Badge variant={etatVariant}>{etatLabel}</Badge>
      </TableCell>

      {/* Patient */}
      <TableCell className="text-sm">
        {r.patient_id ? (
          <Link
            to={`/patients/${r.patient_id}`}
            className="text-navy hover:underline"
          >
            {r.patient_display ?? `#${r.patient_id}`}
          </Link>
        ) : (
          <span className="text-muted">—</span>
        )}
      </TableCell>

      {/* Actions */}
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-1.5">
          {canEdit && (
            <Button variant="ghost" size="sm" onClick={onEdit}>
              Modifier
            </Button>
          )}
          {['du', 'a_envoyer'].includes(r.etat) && (
            <Button variant="ghost" size="sm" onClick={onIgnorer}>
              Ignorer
            </Button>
          )}
          {r.etat === 'a_envoyer' && (
            <Button
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={onSendWhatsApp}
            >
              <WhatsAppIcon className="size-3.5" /> Envoyer
            </Button>
          )}
          {['du', 'a_envoyer'].includes(r.etat) && (
            <Button variant="outline" size="sm" onClick={onTraite}>
              Traité
            </Button>
          )}
          {['planifie'].includes(r.etat) && (
            <Button
              variant="ghost"
              size="sm"
              className="text-red hover:text-red"
              onClick={onAnnuler}
            >
              Annuler
            </Button>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
