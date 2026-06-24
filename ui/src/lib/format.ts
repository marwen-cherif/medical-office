/**
 * Formatage et libellés partagés (dates FR, montants, statuts), repris des cartes
 * de libellés en tête de `crm/app.py` (_STATUT_LABELS, _MODE_LABELS, …).
 */
import type { BadgeProps } from "@/components/ui/badge";

type BadgeVariant = NonNullable<BadgeProps["variant"]>;

/** Montant FR : espace fine pour les milliers, virgule décimale, 2 décimales. */
export function fmtMontant(value: number | null | undefined): string {
  const n = value ?? 0;
  return n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** `1 800,00 €`. */
export function fmtEuro(value: number | null | undefined): string {
  return `${fmtMontant(value)} €`;
}

/** ISO `YYYY-MM-DD` → `DD/MM/YYYY` (chaîne vide si absente/illisible). */
export function isoToFr(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}/${m[2]}/${m[1]}`;
}

/** Horodatage ISO → `DD/MM/YYYY HH:MM`. */
export function isoToFrDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(iso);
  if (!m) return isoToFr(iso);
  return `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}`;
}

/** Date du jour en ISO (`YYYY-MM-DD`), en heure locale. */
export function todayIso(): string {
  const d = new Date();
  const z = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

/** Bornes ISO du mois courant (filtres financiers par défaut). */
export function monthRange(): { from: string; to: string } {
  const d = new Date();
  const z = (n: number) => String(n).padStart(2, "0");
  const first = `${d.getFullYear()}-${z(d.getMonth() + 1)}-01`;
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  const to = `${last.getFullYear()}-${z(last.getMonth() + 1)}-${z(last.getDate())}`;
  return { from: first, to };
}

/** Transforme un tag/type machine en libellé lisible (`note_honoraires` → `Note honoraires`). */
export function humanize(tag: string | null | undefined): string {
  if (!tag) return "";
  const s = tag.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// --- Statuts de documents (cf. _STATUT_LABELS) -------------------------------
export const DOC_STATUTS: Record<string, { label: string; variant: BadgeVariant }> = {
  brouillon: { label: "Brouillon", variant: "outline" },
  genere: { label: "Généré", variant: "muted" },
  en_attente_envoi: { label: "En attente d'envoi", variant: "default" },
  envoye: { label: "Envoyé", variant: "success" },
  erreur: { label: "Erreur génération", variant: "danger" },
  erreur_envoi: { label: "Erreur envoi", variant: "danger" },
};

export function docStatut(statut: string): { label: string; variant: BadgeVariant } {
  return DOC_STATUTS[statut] ?? { label: humanize(statut), variant: "muted" };
}

// --- Statuts de dépenses (cf. _DEPENSE_STATUT_LABELS) ------------------------
export const DEPENSE_STATUTS: Record<string, { label: string; variant: BadgeVariant }> = {
  en_attente: { label: "À régler", variant: "default" },
  regle_partiellement: { label: "Réglé partiellement", variant: "outline" },
  regle: { label: "Réglé", variant: "success" },
};

export function depenseStatut(statut: string): { label: string; variant: BadgeVariant } {
  return DEPENSE_STATUTS[statut] ?? { label: humanize(statut), variant: "muted" };
}

// --- Statuts de jobs (cf. _JOB_STATUT_LABELS) --------------------------------
export const JOB_STATUTS: Record<string, { label: string; variant: BadgeVariant }> = {
  en_cours: { label: "En cours", variant: "default" },
  termine: { label: "Terminé", variant: "success" },
  termine_partiel: { label: "Succès partiel", variant: "outline" },
  erreur: { label: "Erreur", variant: "danger" },
  interrompu: { label: "Interrompu", variant: "outline" },
};

export function jobStatut(statut: string): { label: string; variant: BadgeVariant } {
  return JOB_STATUTS[statut] ?? { label: humanize(statut), variant: "muted" };
}

export const JOB_ITEM_STATUTS: Record<string, { label: string; variant: BadgeVariant }> = {
  ok: { label: "OK", variant: "success" },
  skip: { label: "Ignoré", variant: "muted" },
  erreur: { label: "Erreur", variant: "danger" },
};

// --- Modes de paiement (cf. _MODE_LABELS) ------------------------------------
export const MODE_LABELS: Record<string, string> = {
  especes: "Espèces",
  cheque: "Chèque",
  carte: "Carte",
  virement: "Virement",
};

export const MODE_OPTIONS = [
  { value: "especes", label: "Espèces" },
  { value: "cheque", label: "Chèque" },
  { value: "carte", label: "Carte" },
  { value: "virement", label: "Virement" },
];

export function modeLabel(mode: string | null | undefined): string {
  if (!mode) return "—";
  return MODE_LABELS[mode] ?? humanize(mode);
}

// --- Notation dentaire FDI (odontogramme) ------------------------------------
// Permanentes par quadrant (1-4) et temporaires (5-8), notation FDI.
export const DENTS_PERMANENTES: Record<number, string[]> = {
  1: ["18", "17", "16", "15", "14", "13", "12", "11"],
  2: ["21", "22", "23", "24", "25", "26", "27", "28"],
  4: ["48", "47", "46", "45", "44", "43", "42", "41"],
  3: ["31", "32", "33", "34", "35", "36", "37", "38"],
};

export const DENTS_TEMPORAIRES: Record<number, string[]> = {
  5: ["55", "54", "53", "52", "51"],
  6: ["61", "62", "63", "64", "65"],
  8: ["85", "84", "83", "82", "81"],
  7: ["71", "72", "73", "74", "75"],
};

/** Découpe une chaîne de dents (`"26, 27"`) en liste. */
export function parseDents(raw: string | null | undefined): string[] {
  if (!raw) return [];
  return raw
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}
