/**
 * Catégories de modèles « métier », **statiques dans le code**.
 *
 * Contrairement aux catégories libres saisies par l'utilisateur (table `categories`,
 * créées paresseusement), celles-ci pilotent une **logique applicative** et sont donc
 * figées ici. Elles sont **toujours suggérées** dans le sélecteur de catégorie (même si
 * aucun modèle ne les utilise encore), pour qu'un modèle puisse être rangé au bon
 * endroit et activer la logique associée.
 *
 * `NOTE_HONORAIRE_CATEGORIE` doit rester aligné sur le défaut backend
 * `NOTE_CAT_DEFAULT` (`crm/routers/documents.py`) : le bouton « Note d'honoraires »
 * (fiche patient) ne propose que les modèles de cette catégorie.
 */
export const NOTE_HONORAIRE_CATEGORIE = "Notes d'honoraires";

/** Catégories spéciales suggérées en priorité (libellé → courte explication métier). */
export const SPECIAL_CATEGORIES: { nom: string; hint: string }[] = [
  {
    nom: NOTE_HONORAIRE_CATEGORIE,
    hint: "Alimente le bouton « Note d'honoraires » de la fiche patient.",
  },
];
