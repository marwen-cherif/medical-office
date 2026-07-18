/**
 * Helpers de présentation pour les rappels (libellés, variantes de badge).
 */
import type { BadgeProps } from '@/components/ui/badge';
import type { RappelEtat, RappelType } from '@/api/types';

type BadgeVariant = NonNullable<BadgeProps['variant']>;

export const RAPPEL_ETAT_CONFIG: Record<RappelEtat, { label: string; variant: BadgeVariant }> = {
  planifie: { label: 'Planifié', variant: 'outline' },
  du: { label: 'Dû', variant: 'default' },
  a_envoyer: { label: 'À envoyer', variant: 'default' },
  envoye: { label: 'Envoyé', variant: 'success' },
  traite: { label: 'Traité', variant: 'success' },
  annule: { label: 'Annulé', variant: 'muted' },
};

export function rappelEtatBadge(etat: string): { label: string; variant: BadgeVariant } {
  return RAPPEL_ETAT_CONFIG[etat as RappelEtat] ?? { label: etat, variant: 'muted' };
}

export const RAPPEL_TYPE_LABELS: Record<RappelType, string> = {
  alerte_interne: 'Alerte interne',
  message_patient: 'Message patient WhatsApp',
};

export function rappelTypeLabel(type: string): string {
  return RAPPEL_TYPE_LABELS[type as RappelType] ?? type;
}
