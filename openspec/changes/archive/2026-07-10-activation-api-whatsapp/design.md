## Context

Pour simplifier l'expérience utilisateur, le cabinet médical souhaite ne voir que les menus de réglages correspondant aux fonctionnalités qu'il utilise réellement. Un nouvel onglet « Fonctionnalités » (Feature Flags) centralisera ces options d'activation.

## Goals / Non-Goals

**Goals:**
- Ajouter un onglet « Fonctionnalités » dans Paramétrage pour activer/désactiver des fonctionnalités à la volée.
- Afficher/masquer dynamiquement l'onglet de réglages « WhatsApp » dans la navigation latérale de Paramétrage selon que la fonctionnalité est activée.
- Masquer le bouton d'envoi automatique Meta Cloud côté patient si la fonctionnalité est désactivée.

**Non-Goals:**
- Créer une structure de base de données complexe de feature flags. La persistance clé-valeur actuelle dans la table `meta` avec le champ `whatsapp_api_enabled` est réutilisée.

## Decisions

### D1 — Nouvel Onglet « Fonctionnalités » (`FonctionnalitesTab.tsx`)
Création d'un composant frontend `apps/web/src/screens/parametrage/FonctionnalitesTab.tsx` qui affiche la liste des fonctionnalités activables. Cet onglet manipule directement le flag `whatsapp_api_enabled` via les hooks de paramétrage WhatsApp.

### D2 — Visibilité dynamique de l'onglet dans `Parametrage.tsx`
Dans `Parametrage.tsx`, la liste `items` du sous-menu latéral filtre dynamiquement l'onglet `"whatsapp"` en fonction de la valeur de `whatsapp_api_enabled` retournée par le hook `useWhatsAppSettings()`.

### D3 — Maintien des vérifications de sécurité
L'endpoint d'envoi et les boutons côté patient restent conditionnés par le statut d'activation du flag en base pour garantir la cohérence technique.

## Risks / Trade-offs

- **[Risk] Onglet WhatsApp caché avec identifiants configurés** → Si un utilisateur désactive par erreur la fonctionnalité WhatsApp dans l'onglet Fonctionnalités, il ne verra plus l'onglet de paramétrage WhatsApp, mais ses identifiants configurés restent intacts en base.
  - *Mitigation* : Le fait de réactiver l'option fait réapparaître l'onglet avec tous ses identifiants pré-remplis sans aucune perte de données.
