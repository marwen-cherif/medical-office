/**
 * Formatage et libellés partagés (dates FR, montants, statuts), repris des cartes
 * de libellés en tête de `crm/app.py` (_STATUT_LABELS, _MODE_LABELS, …).
 */
import type { BadgeProps } from '@/components/ui/badge';

type BadgeVariant = NonNullable<BadgeProps['variant']>;

// --- Devise de l'application -------------------------------------------------
// La devise est choisie au build via la variable d'environnement Vite
// `VITE_DEVISE` (valeurs : "EUR" par défaut, ou "TND"). Le symbole affiché et le
// nombre de décimales en découlent. Pour en ajouter une, compléter `DEVISES`.
// Voir aussi `ui/.env.example`.
type DeviseConfig = { code: string; symbole: string; decimales: number };

const DEVISES: Record<string, DeviseConfig> = {
  EUR: { code: 'EUR', symbole: '€', decimales: 2 },
  TND: { code: 'TND', symbole: 'DT', decimales: 3 },
};

/** Devise courante, résolue depuis `VITE_DEVISE` (repli sur l'euro si inconnue). */
export const DEVISE: DeviseConfig =
  DEVISES[(import.meta.env.VITE_DEVISE ?? 'EUR').toUpperCase()] ?? DEVISES.EUR;

/** Symbole de la devise courante (`€`, `DT`, …) — pour les libellés de champs. */
export const DEVISE_SYMBOLE = DEVISE.symbole;

/** Montant FR : espace (visible) pour les milliers, virgule décimale, décimales selon la devise. */
export function fmtMontant(value: number | null | undefined): string {
  const n = value ?? 0;
  return (
    n
      .toLocaleString('fr-FR', {
        minimumFractionDigits: DEVISE.decimales,
        maximumFractionDigits: DEVISE.decimales,
      })
      // `fr-FR` sépare les milliers par une espace fine insécable (U+202F) ou
      // insécable (U+00A0) qui, selon la police, ne s'affiche pas : le montant
      // paraît « collé » (10000,801). On la normalise en espace ordinaire visible.
      .replace(/[\u202f\u00a0]/g, ' ')
  );
}

/** Montant suivi du symbole de la devise courante (`1 800,00 €`, `1 800,000 DT`). */
export function fmtDevise(value: number | null | undefined): string {
  return `${fmtMontant(value)} ${DEVISE.symbole}`;
}

/**
 * Valeur pour un champ de saisie de montant : décimales de la devise, point
 * décimal (jamais de séparateur de milliers). Remplace les `toFixed(2)` codés en
 * dur, qui tronquaient la 3ᵉ décimale en TND.
 */
export function montantInput(value: number | null | undefined): string {
  return (value ?? 0).toFixed(DEVISE.decimales);
}

/** ISO `YYYY-MM-DD` → `DD/MM/YYYY` (chaîne vide si absente/illisible). */
export function isoToFr(iso: string | null | undefined): string {
  if (!iso) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}/${m[2]}/${m[1]}`;
}

/** Horodatage ISO → `DD/MM/YYYY HH:MM`. */
export function isoToFrDateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(iso);
  if (!m) return isoToFr(iso);
  return `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}`;
}

/** Date du jour en ISO (`YYYY-MM-DD`), en heure locale. */
export function todayIso(): string {
  return dateToIso(new Date());
}

/** `Date` → ISO `YYYY-MM-DD` en heure locale (pas de décalage UTC). */
export function dateToIso(d: Date): string {
  const z = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

/**
 * ISO `YYYY-MM-DD` → `Date` locale (minuit), ou `undefined` si absente/illisible.
 * Construit la date composant par composant pour éviter l'interprétation UTC de
 * `new Date("YYYY-MM-DD")`, qui décalerait d'un jour selon le fuseau.
 */
export function isoToDate(iso: string | null | undefined): Date | undefined {
  if (!iso) return undefined;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return undefined;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

/**
 * Masque une saisie clavier en `JJ/MM/AAAA` : ne garde que les chiffres (8 au plus)
 * et réinsère les `/` automatiquement. Permet de taper `27101990` → `27/10/1990`
 * sans saisir les séparateurs (accessibilité clavier des champs date).
 */
export function maskDateFr(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 8);
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4, 8)].filter(Boolean).join('/');
}

/**
 * `JJ/MM/AAAA` → ISO `YYYY-MM-DD`, ou chaîne vide si la date est incomplète ou
 * invalide (rejette p. ex. `31/02/2020` via une re-vérification des composants).
 */
export function frToIso(fr: string | null | undefined): string {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec((fr ?? '').trim());
  if (!m) return '';
  const day = Number(m[1]);
  const month = Number(m[2]);
  const year = Number(m[3]);
  const d = new Date(year, month - 1, day);
  if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) return '';
  return dateToIso(d);
}

/** Bornes ISO du mois courant (filtres financiers par défaut). */
export function monthRange(): { from: string; to: string } {
  const d = new Date();
  const z = (n: number) => String(n).padStart(2, '0');
  const first = `${d.getFullYear()}-${z(d.getMonth() + 1)}-01`;
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  const to = `${last.getFullYear()}-${z(last.getMonth() + 1)}-${z(last.getDate())}`;
  return { from: first, to };
}

/** Plage ISO `[premierJour, dernierJour]` du mois `m` (0–11) de l'année `y`. */
function monthBounds(y: number, m: number): { from: string; to: string } {
  const z = (n: number) => String(n).padStart(2, '0');
  const last = new Date(y, m + 1, 0);
  return {
    from: `${y}-${z(m + 1)}-01`,
    to: `${last.getFullYear()}-${z(last.getMonth() + 1)}-${z(last.getDate())}`,
  };
}

/** Plage ISO du trimestre civil (1–4) contenant/adjacent à la date `d`. */
function quarterBounds(y: number, q: number): { from: string; to: string } {
  const z = (n: number) => String(n).padStart(2, '0');
  const startMonth = (q - 1) * 3; // Q1→0, Q2→3, Q3→6, Q4→9
  const last = new Date(y, startMonth + 3, 0); // dernier jour du 3ᵉ mois du trimestre
  return { from: `${y}-${z(startMonth + 1)}-01`, to: dateToIso(last) };
}

export type DatePresetKey =
  | 'ce_mois'
  | 'mois_dernier'
  | 'ce_trimestre'
  | 'trimestre_dernier'
  | 'cette_annee'
  | 'annee_derniere';

export type DatePreset = {
  key: DatePresetKey;
  label: string;
  range: { from: string; to: string };
};

/**
 * Plages prédéfinies relatives à la date du jour, pour pré-remplir le filtre de
 * période. Calculées dynamiquement (et non mémorisées) afin que « ce mois »
 * reste correct si le popover reste ouvert au passage de minuit.
 */
export function datePresets(now: Date = new Date()): DatePreset[] {
  const y = now.getFullYear();
  const m = now.getMonth();
  const q = Math.floor(m / 3) + 1;
  const prevQ = q === 1 ? { y: y - 1, q: 4 } : { y, q: q - 1 };
  return [
    { key: 'ce_mois', label: 'Ce mois', range: monthBounds(y, m) },
    { key: 'mois_dernier', label: 'Le mois dernier', range: monthBounds(m === 0 ? y - 1 : y, m === 0 ? 11 : m - 1) },
    { key: 'ce_trimestre', label: 'Ce trimestre', range: quarterBounds(y, q) },
    { key: 'trimestre_dernier', label: 'Le trimestre dernier', range: quarterBounds(prevQ.y, prevQ.q) },
    { key: 'cette_annee', label: 'Cette année', range: { from: `${y}-01-01`, to: `${y}-12-31` } },
    { key: 'annee_derniere', label: "L'année dernière", range: { from: `${y - 1}-01-01`, to: `${y - 1}-12-31` } },
  ];
}

/** Clé du preset correspondant à une plage donnée, ou `null` si aucune ne correspond. */
export function findDatePreset(
  from: string,
  to: string,
  now: Date = new Date()
): DatePresetKey | null {
  const hit = datePresets(now).find(
    (p) => p.range.from === from && p.range.to === to
  );
  return hit ? hit.key : null;
}

/** Transforme un tag/type machine en libellé lisible (`note_honoraires` → `Note honoraires`). */
export function humanize(tag: string | null | undefined): string {
  if (!tag) return '';
  const s = tag.replace(/_/g, ' ').trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// --- Statuts de documents (cf. _STATUT_LABELS) -------------------------------
export const DOC_STATUTS: Record<string, { label: string; variant: BadgeVariant }> = {
  brouillon: { label: 'Brouillon', variant: 'outline' },
  genere: { label: 'Généré', variant: 'muted' },
  en_attente_envoi: { label: "En attente d'envoi", variant: 'default' },
  envoye: { label: 'Envoyé', variant: 'success' },
  erreur: { label: 'Erreur génération', variant: 'danger' },
  erreur_envoi: { label: 'Erreur envoi', variant: 'danger' },
};

export function docStatut(statut: string): { label: string; variant: BadgeVariant } {
  return DOC_STATUTS[statut] ?? { label: humanize(statut), variant: 'muted' };
}

// --- Statuts de dépenses (cf. _DEPENSE_STATUT_LABELS) ------------------------
export const DEPENSE_STATUTS: Record<string, { label: string; variant: BadgeVariant }> = {
  en_attente: { label: 'À régler', variant: 'default' },
  regle_partiellement: { label: 'Réglé partiellement', variant: 'outline' },
  regle: { label: 'Réglé', variant: 'success' },
};

export function depenseStatut(statut: string): { label: string; variant: BadgeVariant } {
  return DEPENSE_STATUTS[statut] ?? { label: humanize(statut), variant: 'muted' };
}

// --- Statuts de jobs (cf. _JOB_STATUT_LABELS) --------------------------------
export const JOB_STATUTS: Record<string, { label: string; variant: BadgeVariant }> = {
  en_cours: { label: 'En cours', variant: 'default' },
  termine: { label: 'Terminé', variant: 'success' },
  termine_partiel: { label: 'Succès partiel', variant: 'outline' },
  erreur: { label: 'Erreur', variant: 'danger' },
  interrompu: { label: 'Interrompu', variant: 'outline' },
};

export function jobStatut(statut: string): { label: string; variant: BadgeVariant } {
  return JOB_STATUTS[statut] ?? { label: humanize(statut), variant: 'muted' };
}

export const JOB_ITEM_STATUTS: Record<string, { label: string; variant: BadgeVariant }> = {
  ok: { label: 'OK', variant: 'success' },
  skip: { label: 'Ignoré', variant: 'muted' },
  erreur: { label: 'Erreur', variant: 'danger' },
};

// --- Modes de paiement (cf. _MODE_LABELS) ------------------------------------
export const MODE_LABELS: Record<string, string> = {
  especes: 'Espèces',
  cheque: 'Chèque',
  carte: 'Carte',
  virement: 'Virement',
};

export const MODE_OPTIONS = [
  { value: 'especes', label: 'Espèces' },
  { value: 'cheque', label: 'Chèque' },
  { value: 'carte', label: 'Carte' },
  { value: 'virement', label: 'Virement' },
];

export function modeLabel(mode: string | null | undefined): string {
  if (!mode) return '—';
  return MODE_LABELS[mode] ?? humanize(mode);
}

// --- Notation dentaire FDI (odontogramme) ------------------------------------
// Permanentes par quadrant (1-4) et temporaires (5-8), notation FDI.
export const DENTS_PERMANENTES: Record<number, string[]> = {
  1: ['18', '17', '16', '15', '14', '13', '12', '11'],
  2: ['21', '22', '23', '24', '25', '26', '27', '28'],
  4: ['48', '47', '46', '45', '44', '43', '42', '41'],
  3: ['31', '32', '33', '34', '35', '36', '37', '38'],
};

export const DENTS_TEMPORAIRES: Record<number, string[]> = {
  5: ['55', '54', '53', '52', '51'],
  6: ['61', '62', '63', '64', '65'],
  8: ['85', '84', '83', '82', '81'],
  7: ['71', '72', '73', '74', '75'],
};

/** Découpe une chaîne de dents (`"26, 27"`) en liste. */
export function parseDents(raw: string | null | undefined): string[] {
  if (!raw) return [];
  return raw
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function formatWaMeUrl(phone: string, defaultCountry: string, text: string): string {
  let digits = phone.replace(/[^\d]/g, '');
  if (phone.startsWith('00')) {
    digits = digits.slice(2);
  } else if (phone.startsWith('+')) {
    // Keep digits from slice
  } else {
    if (digits.startsWith('0')) {
      digits = digits.slice(1);
    }
    const countryDigits = defaultCountry.replace(/[^\d]/g, '') || '216';
    digits = countryDigits + digits;
  }
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
}

export type CountryConfig = { code: string; name: string; prefix: string; flag: string };

export const COUNTRIES: CountryConfig[] = [
  { code: 'TN', name: 'Tunisie', prefix: '+216', flag: '🇹🇳' },
  { code: 'FR', name: 'France', prefix: '+33', flag: '🇫🇷' },
  { code: 'DZ', name: 'Algérie', prefix: '+213', flag: '🇩🇿' },
  { code: 'MA', name: 'Maroc', prefix: '+212', flag: '🇲🇦' },
  { code: 'LY', name: 'Libye', prefix: '+218', flag: '🇱🇾' },
  { code: 'BE', name: 'Belgique', prefix: '+32', flag: '🇧🇪' },
  { code: 'CH', name: 'Suisse', prefix: '+41', flag: '🇨🇭' },
  { code: 'CA', name: 'Canada', prefix: '+1', flag: '🇨🇦' },
];

export function parsePhoneNumber(
  phoneStr: string,
  defaultPrefix = '+216'
): { prefix: string; local: string } {
  if (!phoneStr) return { prefix: defaultPrefix, local: '' };

  let clean = phoneStr.replace(/[\s\-\(\)]/g, '');

  if (clean.startsWith('00')) {
    clean = '+' + clean.substring(2);
  }

  const sortedCountries = [...COUNTRIES].sort((a, b) => b.prefix.length - a.prefix.length);

  for (const country of sortedCountries) {
    if (clean.startsWith(country.prefix)) {
      let local = clean.substring(country.prefix.length);
      if (local.startsWith('0')) {
        local = local.substring(1);
      }
      return { prefix: country.prefix, local };
    }
  }

  if (clean.startsWith('+')) {
    const match = clean.match(/^(\+\d{1,4})(.*)$/);
    if (match) {
      let local = match[2];
      if (local.startsWith('0')) local = local.substring(1);
      return { prefix: match[1], local };
    }
  }

  let local = clean;
  if (local.startsWith('0') && !local.startsWith('00')) {
    local = local.substring(1);
  }

  return { prefix: defaultPrefix, local };
}

export function formatE164(prefix: string, local: string): string {
  let cleanLocal = local.replace(/[\s\-\(\)]/g, '');
  if (cleanLocal.startsWith('0')) {
    cleanLocal = cleanLocal.substring(1);
  }
  if (!cleanLocal) return '';
  return `${prefix}${cleanLocal}`;
}
