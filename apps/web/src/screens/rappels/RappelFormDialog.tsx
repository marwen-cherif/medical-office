/**
 * Formulaire création / édition d'un rappel.
 *
 * Modes :
 *   - `target = null`    → dialog fermé
 *   - `target = 'new'`   → création
 *   - `target = Rappel`  → édition (champs pré-remplis)
 *
 * Props :
 *   - `defaultPatientId`  : passé depuis la fiche patient — jamais saisi manuellement.
 *   - `defaultDocumentId` : passé après envoi d'un document.
 *
 * Champs visibles :
 *   - Type (alerte_interne | message_patient)
 *   - Titre  (obligatoire)
 *   - Description / notes  (tous types — pourquoi ce rappel a été programmé)
 *   - Échéance + raccourcis rapides
 *   - Message WhatsApp  (message_patient uniquement, obligatoire)
 *
 * patient_id et document_id sont toujours transmis en hidden via les props,
 * jamais exposés comme champ de saisie.
 */
import { useEffect, useState } from 'react';
import { Loader2, Save } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { DatePicker } from '@/components/common/DatePicker';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { humanizeError } from '@/lib/errors';
import { todayIso, dateToIso } from '@/lib/format';
import { useCreateRappel, useUpdateRappel } from '@/hooks/rappels';
import type { Rappel, RappelType } from '@/api/types';

// ---------------------------------------------------------------------------
// Raccourcis d'échéance rapide
// ---------------------------------------------------------------------------
const ECHEANCES_RAPIDES = [
  { label: '+1 semaine', days: 7 },
  { label: '+1 mois', days: 30 },
  { label: '+2 mois', days: 60 },
  { label: '+3 mois', days: 90 },
];

function addDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return dateToIso(d);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface Props {
  target: Rappel | 'new' | null;
  onClose: () => void;
  /** Transmis silencieusement — jamais saisi par l'utilisateur. */
  defaultPatientId?: number | null;
  defaultDocumentId?: number | null;
}

// ---------------------------------------------------------------------------
// Composant
// ---------------------------------------------------------------------------
export function RappelFormDialog({ target, onClose, defaultPatientId, defaultDocumentId }: Props) {
  const isOpen = target !== null;
  const isEdit = target !== null && target !== 'new';

  const [type, setType] = useState<RappelType>('alerte_interne');
  const [titre, setTitre] = useState('');
  const [description, setDescription] = useState('');
  const [echeance, setEcheance] = useState(todayIso());
  const [message, setMessage] = useState('');

  const create = useCreateRappel();
  const update = useUpdateRappel();
  const isSaving = create.isPending || update.isPending;

  // patient_id / document_id : toujours passés en props, jamais modifiables
  const patientId = isEdit
    ? (target.patient_id ?? defaultPatientId ?? null)
    : (defaultPatientId ?? null);
  const documentId = isEdit
    ? (target.document_id ?? defaultDocumentId ?? null)
    : (defaultDocumentId ?? null);

  // Remplissage initial à l'ouverture
  useEffect(() => {
    if (!isOpen) return;
    if (isEdit) {
      setType(target.type);
      setTitre(target.titre);
      setEcheance((target.echeance ?? '').slice(0, 10));
      // `message` stocke à la fois la description (alerte) et le message WA
      setDescription(target.message ?? '');
      setMessage(target.message ?? '');
    } else {
      setType('alerte_interne');
      setTitre('');
      setDescription('');
      setEcheance(todayIso());
      setMessage('');
    }
  }, [isOpen, target]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!titre.trim()) {
      toast.error('Le titre est obligatoire.');
      return;
    }
    if (!echeance) {
      toast.error("L'échéance est obligatoire.");
      return;
    }
    if (type === 'message_patient' && !patientId) {
      toast.error("Ce rappel doit être créé depuis la fiche d'un patient.");
      return;
    }
    if (type === 'message_patient' && !message.trim()) {
      toast.error('Le message WhatsApp est obligatoire.');
      return;
    }

    // Pour alerte_interne : on stocke la description dans le champ `message`
    // (colonne polyvalente — le backend ne distingue pas les deux).
    const messageToSend =
      type === 'message_patient' ? message.trim() || null : description.trim() || null;

    const body = {
      type,
      titre: titre.trim(),
      echeance,
      message: messageToSend,
      patient_id: patientId,
      document_id: documentId,
    };

    if (isEdit) {
      update.mutate(
        { id: target.id, body },
        {
          onSuccess: () => {
            toast.success('Rappel mis à jour.');
            onClose();
          },
          onError: (e) => toast.error(humanizeError(e)),
        }
      );
    } else {
      create.mutate(body, {
        onSuccess: () => {
          toast.success('Rappel créé.');
          onClose();
        },
        onError: (e) => toast.error(humanizeError(e)),
      });
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Modifier le rappel' : 'Nouveau rappel'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Type */}
          <div className="space-y-1.5">
            <Label htmlFor="rappel-type">Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as RappelType)}>
              <SelectTrigger id="rappel-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="alerte_interne">🔔 Alerte interne</SelectItem>
                <SelectItem value="message_patient">💬 Message patient (WhatsApp)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Titre */}
          <div className="space-y-1.5">
            <Label htmlFor="rappel-titre">Titre</Label>
            <Input
              id="rappel-titre"
              value={titre}
              onChange={(e) => setTitre(e.target.value)}
              placeholder={
                type === 'message_patient'
                  ? 'ex. Rappel RDV contrôle'
                  : 'ex. Relancer le fournisseur'
              }
              autoFocus
            />
          </div>

          {/* Description (tous types) */}
          <div className="space-y-1.5">
            <Label htmlFor="rappel-description">
              {type === 'message_patient' ? 'Note interne' : 'Description'}
              <span className="ml-1 text-xs text-muted font-normal">(optionnel)</span>
            </Label>
            <Textarea
              id="rappel-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder={
                type === 'message_patient'
                  ? 'Note pour vous-même sur ce rappel…'
                  : 'Pourquoi ce rappel a été programmé…'
              }
            />
          </div>

          {/* Échéance */}
          <div className="space-y-1.5">
            <Label htmlFor="rappel-echeance">Échéance</Label>
            <DatePicker
              id="rappel-echeance"
              value={echeance}
              onChange={setEcheance}
            />
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              {ECHEANCES_RAPIDES.map((r) => (
                <button
                  key={r.label}
                  type="button"
                  onClick={() => setEcheance(addDays(r.days))}
                  className="rounded border border-line bg-bg px-2 py-0.5 text-xs text-ink hover:bg-white transition-colors"
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          {/* Message WhatsApp — message_patient uniquement */}
          {type === 'message_patient' && (
            <div className="space-y-1.5">
              <Label htmlFor="rappel-message">
                Message WhatsApp <span className="text-red">*</span>
              </Label>
              <Textarea
                id="rappel-message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={3}
                placeholder="Bonjour, votre prochain rendez-vous est le…"
              />
            </div>
          )}

          {/* Contexte patient / document (informatif si présent, non modifiable) */}
          {(patientId != null || documentId != null) && (
            <p className="text-xs text-muted">
              {patientId != null && (
                <>
                  Patient #{patientId}
                  {documentId != null ? ' · ' : ''}
                </>
              )}
              {documentId != null && <>Document #{documentId}</>}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={isSaving}>
              Annuler
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
              {isEdit ? 'Enregistrer' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
