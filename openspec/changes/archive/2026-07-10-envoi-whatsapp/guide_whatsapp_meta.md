# Guide de Configuration WhatsApp Business API

> [!IMPORTANT]
> Ce guide vous permet de configurer l'envoi automatique de documents par WhatsApp depuis votre logiciel de cabinet. Durée estimée : **15-20 minutes** (une seule fois).

---

## Étape 1 — Créer un compte Meta Business

1. Rendez-vous sur [business.facebook.com](https://business.facebook.com)
2. Cliquez sur **Créer un compte**
3. Renseignez :
   - Le nom du cabinet (ex. « Cabinet Dr. Ben Ahmed »)
   - Votre nom
   - Une adresse email professionnelle
4. Validez l'email de confirmation

> [!TIP]
> Vous n'avez pas besoin d'une page Facebook active. Le compte Business suffit.

---

## Étape 2 — Accéder à l'API WhatsApp

1. Allez sur [developers.facebook.com](https://developers.facebook.com)
2. Cliquez sur **Mes applications** → **Créer une application**
3. Sélectionnez le type **Business**
4. Donnez un nom (ex. « Cabinet WhatsApp »)
5. Associez-la à votre compte Meta Business créé à l'étape 1
6. Dans le tableau de bord de l'application, cherchez **WhatsApp** et cliquez **Configurer**

---

## Étape 3 — Configurer votre numéro de téléphone

1. Dans la section **WhatsApp** → **Démarrage rapide** :
   - Meta vous attribue un **numéro de test gratuit** pour essayer
   - Pour la production, cliquez **Ajouter un numéro de téléphone**
2. Saisissez le numéro du cabinet (ex. `+216 XX XXX XXX`)
3. Validez par SMS ou appel vocal
4. **Notez le Phone Number ID** affiché (un grand nombre comme `104829302948294`)

> [!WARNING]
> Le numéro ajouté sera dissocié de l'application WhatsApp classique. Utilisez un numéro dédié au cabinet (pas votre numéro personnel).

---

## Étape 4 — Créer le modèle de message

C'est l'étape la plus importante. Un seul modèle suffit pour tous vos documents.

1. Allez dans **WhatsApp** → **Gestion** → **Modèles de messages**
2. Cliquez **Créer un modèle**
3. Remplissez :

| Champ | Valeur |
|---|---|
| **Catégorie** | `Utility` |
| **Nom** | `envoi_document` |
| **Langue** | `Français (fr)` |

4. Configurez le **Header** (En-tête) :
   - Type : **Document**
   - *(Cela permet d'envoyer n'importe quel PDF en pièce jointe)*

5. Configurez le **Body** (Corps du message) :
   ```
   Bonjour {{1}} {{2}}, veuillez trouver ci-joint votre {{3}}. Cabinet Dr. [Votre Nom]
   ```
   - `{{1}}` = Prénom du patient (rempli automatiquement)
   - `{{2}}` = Nom du patient (rempli automatiquement)
   - `{{3}}` = Type de document : « note d'honoraires », « devis », etc. (rempli automatiquement)

6. Ajoutez des **exemples** pour chaque variable (requis par Meta) :
   - `{{1}}` → `Ahmed`
   - `{{2}}` → `Ben Ali`
   - `{{3}}` → `note d'honoraires`

7. Cliquez **Soumettre**

> [!NOTE]
> L'approbation du modèle prend généralement entre **1 minute et 24 heures**. Les modèles `Utility` sont approuvés rapidement.

---

## Étape 5 — Générer un Token d'accès permanent

1. Dans l'application Facebook Developer, allez dans **Paramètres système** → **Utilisateurs**
2. Cliquez **Ajouter un utilisateur système** (type : Admin)
3. Attribuez l'actif WhatsApp à cet utilisateur
4. Cliquez **Générer un token** avec les permissions :
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
5. **Copiez le token** — il ne sera affiché qu'une seule fois !

> [!CAUTION]
> Ce token donne accès à l'envoi de messages WhatsApp depuis votre compte. Ne le partagez jamais et ne le publiez nulle part.

---

## Étape 6 — Configurer dans le logiciel

1. Ouvrez le logiciel → **Paramétrage** → onglet **WhatsApp**
2. Renseignez les 3 champs :

| Champ | Exemple |
|---|---|
| **Phone Number ID** | `104829302948294` |
| **Token d'accès** | *(collez le token copié à l'étape 5)* |
| **Indicatif pays** | `+216` *(Tunisie, par défaut)* |

3. Le **Nom du modèle** est pré-rempli à `envoi_document` — changez-le uniquement si vous avez choisi un autre nom à l'étape 4
4. Cliquez **Enregistrer**

---

## Étape 7 — Tester l'envoi

1. Ouvrez une fiche patient avec un numéro de téléphone
2. Générez un document (note d'honoraires, devis…)
3. Cliquez le bouton **Envoyer par WhatsApp** (icône 💬)
4. Le patient reçoit le message avec le PDF en pièce jointe

---

## Coûts

| | Détail |
|---|---|
| **Création du compte** | Gratuit |
| **Coût par conversation** | ~0.008 USD (catégorie Utility, zone Afrique/MENA) |
| **Estimation mensuelle** | ~7 USD / mois pour 30 envois/jour |
| **1 000 conversations/mois** | Offertes gratuitement par Meta |

> [!TIP]
> Les 1 000 premières conversations de chaque mois sont gratuites. Un cabinet moyen n'atteindra probablement jamais ce seuil.

---

## Résolution de problèmes

| Problème | Solution |
|---|---|
| « Configuration WhatsApp incomplète » | Vérifiez que le Phone Number ID et le Token sont bien renseignés dans Paramétrage |
| « Modèle non approuvé » | Attendez l'approbation du modèle dans Meta Business Manager (1 min à 24h) |
| Erreur 401 / Token expiré | Régénérez un nouveau token permanent dans les Paramètres système de l'application |
| Le patient ne reçoit pas | Vérifiez que le numéro est correct et que le patient a WhatsApp installé |
| Erreur HTTP 400 | Le format du modèle ne correspond pas — vérifiez le nombre de variables (3 attendues) |
