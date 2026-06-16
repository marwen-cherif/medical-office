# Spec technique — Suivi des dépenses & Prestataires (v6)

> Compagnon d'implémentation du **PRD** (`prd_depenses.md`). Le PRD dit *quoi* ; ce document
> dit *comment*, au niveau code : SQL exact, signatures, pseudocode, câblage `crm/app.py`,
> module d'extraction IA, dépendances et build. Lire la **§9 du PRD** (préservation des
> données) avant toute modification de schéma.
>
> Rappel des décisions structurantes : factures fournisseurs **importées** (jamais générées) ;
> **table `factures` séparée** (migration **purement additive**, `documents` intouchée) ;
> dépenses à **règlement partiel** ; extraction IA du montant (désactivable).

---

## 0. Inventaire de l'existant (points d'ancrage)

| Élément | Emplacement | Réutilisé pour |
|---|---|---|
| `SCHEMA_VERSION`, `_SCHEMA`, `_migrate`, `connect`, `_column_exists` | `crm/db.py:15,45,243,205,238` | Schéma v6 additif |
| `_snapshot_before_migration` (avant `_migrate`) | `crm/db.py:186,219` | Filet pré-migration (déjà OK) |
| `slugify`, `_now` | `crm/repo.py:17,26` | Slugs prestataires, horodatage |
| Patron `Patient`/`create_patient`/`find_matches`/`get_or_create_patient` | `crm/repo.py:32,146,262,274` | Calque `Prestataire` |
| Patron `Paiement`/`create_paiement`/`mark_paiement_encaisse`/`list_paiements_filtered` | `crm/repo.py:90,701,720,806` | Calque `Depense` (étendu partiel) |
| `output_dir`, `patient_dir`, `build_filename` | `crm/generator.py:29,39,54` | Archivage facture importée |
| `load_config`, dataclasses `Config/Mailjet/Mail` | `src/config.py:48,15` | Ajout `AIConfig` (sections `ai_provider_*` / `ai_feature_*`) |
| `requests` (HTTP) | déjà utilisé `src/mailer.py` | Provider Qwen-VL-OCR (HTTP), sans nouvelle dépendance |
| `fitz`/PyMuPDF | déjà utilisé `src/pdf_to_jpg.py` | `as_image_parts` (rasterisation PDF → image pour la vision) |
| Palette, `_STATUT_LABELS`, `_MODE_LABELS`, `PAGE_SIZE` | `crm/app.py:30,43,73,166` | Libellés/couleurs dépense |
| `_build_shell`, `_date_field`, `_pagination`, `_run_busy`, `_toast`, `_show_dialog`, `_btn` | `crm/app.py:325,698,633,657,455,463,424` | Page Prestataires/Finances |
| `show_patients`, `show_patient_detail`, `_patient_dialog` | `crm/app.py:964,1329,2293` | Calque Prestataires |
| `show_paiements`, `_refresh_paiements`, `_encaisser`, `_annuler_paiement` | `crm/app.py:1609,1625,2702,2748` | Onglet Dépenses + modales |
| `_refresh_dashboard`, `_camembert` | `crm/app.py:889,845` | KPI + balance |
| État vues (`current_view`, `_reset_and`, `_page_step`, `_focus_search`, `_new_for_current_view`) | `crm/app.py:193,605,563,552,543` | Vues `prestataires`/`depenses` |

> `documents`, `crm/templates.py`, `src/doc_filler.py`, `src/mailer.py`, `src/pdf_to_jpg.py`
> **ne sont pas modifiés**.

---

## 1. Base de données — `crm/db.py`

### 1.1 `SCHEMA_VERSION`
```python
SCHEMA_VERSION = 6   # était 5
```

### 1.2 Ajouts au bloc statique `_SCHEMA` (tables créées via `CREATE TABLE IF NOT EXISTS`)
À ajouter à la fin de la chaîne `_SCHEMA` (`crm/db.py:45`). Sûr sur base neuve **et** existante
(idempotent par `IF NOT EXISTS`) :

```sql
CREATE TABLE IF NOT EXISTS prestataires (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nom          TEXT NOT NULL,
    prenom       TEXT NOT NULL DEFAULT '',
    slug_nom     TEXT NOT NULL,
    slug_prenom  TEXT NOT NULL,
    email        TEXT,
    telephone    TEXT,
    adresse      TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_prestataires_slug ON prestataires(slug_nom, slug_prenom);

CREATE TABLE IF NOT EXISTS factures (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prestataire_id  INTEGER NOT NULL REFERENCES prestataires(id) ON DELETE CASCADE,
    fichier         TEXT NOT NULL,                       -- chemin archivé (output/prestataires/<slug>/…)
    nom_original    TEXT,                                -- nom du fichier uploadé (affichage)
    montant         REAL,                                -- montant extrait/saisi (info facture)
    libelle         TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_factures_prestataire ON factures(prestataire_id);

CREATE TABLE IF NOT EXISTS depenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prestataire_id  INTEGER NOT NULL REFERENCES prestataires(id) ON DELETE CASCADE,
    facture_id      INTEGER REFERENCES factures(id) ON DELETE SET NULL,
    montant         REAL NOT NULL DEFAULT 0,             -- total dû
    montant_regle   REAL NOT NULL DEFAULT 0,             -- cumul versé
    statut          TEXT NOT NULL DEFAULT 'en_attente',  -- en_attente | regle_partiellement | regle
    mode            TEXT,
    motif           TEXT,
    date_echeance   TEXT,
    date_paiement   TEXT,
    libelle         TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_depenses_prestataire ON depenses(prestataire_id);
```

> **Option historique des versements** (PRD §3.2) : si retenue, ajouter aussi
> `depense_reglements(id, depense_id REFERENCES depenses(id) ON DELETE CASCADE, montant REAL,
> mode TEXT, motif TEXT, date_reglement TEXT, created_at TEXT DEFAULT (datetime('now')))`.
> Pour le MVP, le champ cumulé `depenses.montant_regle` suffit ; commencer sans la table fille.

### 1.3 `_migrate` — rien à transformer
La création est portée par `_SCHEMA` (rejoué à chaque `connect`, `crm/db.py:231`). `_migrate`
(`crm/db.py:243`) reste donc inchangé : **aucune** étape `ALTER`, **aucune** reconstruction.
`documents` n'est pas touchée. C'est le gain de la table séparée.

> Pourquoi ne rien ajouter dans `_migrate` : `executescript(_SCHEMA)` tourne **avant**
> `_migrate` et crée déjà les nouvelles tables sur une base v5. `_migrate` ne sert qu'aux
> `ALTER` (que `executescript` ne fait pas) — ici il n'y en a aucun.

### 1.4 Garde-fous (déjà en place, à vérifier seulement)
- Anti-downgrade : `connect()` lève `SchemaTooNewError` si `disk_version > 6` (`crm/db.py:216`).
- Snapshot pré-migration : `_snapshot_before_migration` tourne pour `disk_version < 6`
  (`crm/db.py:218`) → `backups/pre-migration/cabinet-v5-to-v6-<stamp>.db`. Inchangé.
- `_set_version` écrit `meta.schema_version = '6'` (`crm/db.py:255`). Inchangé.

---

## 2. Couche données — `crm/repo.py`

Mêmes conventions que l'existant : dataclass + `_row_to_*` + fonctions `conn`-first,
`commit()` interne, pagination `limit`/`offset`.

### 2.1 Prestataire (calque direct de Patient, `crm/repo.py:32-282`)
```python
@dataclass
class Prestataire:
    id: Optional[int]
    nom: str
    prenom: str = ""
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None

    @property
    def display(self) -> str:
        return f"{self.nom.upper()} {self.prenom}".strip()
```
Fonctions (copies des équivalents patients, table `prestataires`, réutilisant `slugify`) :
`create_prestataire`, `update_prestataire` (set `updated_at=_now()`), `get_prestataire`,
`list_prestataires(conn, search="", limit=None, offset=0)`,
`count_prestataires(conn, search="")`,
`find_prestataire_matches(conn, nom, prenom)` (égalité `slug_nom`+`slug_prenom`),
`get_or_create_prestataire(conn, nom, prenom, **extra)`.
La clause recherche réutilise telle quelle l'astuce slug de `_patient_filter_clause`
(`crm/repo.py:205-211`) — pas de filtre `email/impayes` ici.

### 2.2 Facture
```python
@dataclass
class Facture:
    id: Optional[int]
    prestataire_id: int
    fichier: str
    nom_original: Optional[str] = None
    montant: Optional[float] = None
    libelle: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
```
`create_facture(conn, f) -> Facture`, `get_facture(conn, id)`,
`list_factures(conn, prestataire_id, limit=None, offset=0)` (ORDER BY id DESC),
`count_factures_for_prestataire(conn, prestataire_id)`,
`delete_facture(conn, id)` (la suppression du **fichier** archivé est gérée côté app/generator,
pas dans le repo — cf. §4.3).

### 2.3 Dépense (Paiement étendu au partiel)
```python
@dataclass
class Depense:
    id: Optional[int]
    prestataire_id: int
    facture_id: Optional[int] = None
    montant: float = 0.0           # total dû
    montant_regle: float = 0.0     # cumul versé
    statut: str = "en_attente"     # en_attente | regle_partiellement | regle
    mode: Optional[str] = None
    motif: Optional[str] = None
    date_echeance: Optional[str] = None
    date_paiement: Optional[str] = None
    libelle: Optional[str] = None
    notes: Optional[str] = None

    @property
    def reste(self) -> float:
        return max(0.0, (self.montant or 0) - (self.montant_regle or 0))
```

**Helper de statut dérivé** (source unique de vérité, à appeler à chaque écriture) :
```python
def statut_depense(montant: float, regle: float) -> str:
    if regle <= 0:
        return "en_attente"
    if regle + 1e-9 < montant:
        return "regle_partiellement"
    return "regle"
```

Fonctions :
- `create_depense(conn, prestataire_id, montant, *, montant_regle=0.0, motif=None,
  facture_id=None, date_echeance=None, mode=None, libelle=None) -> Depense`
  — valide `montant > 0` (calque `create_paiement`, `crm/repo.py:701-704`) et
  `0 <= montant_regle <= montant` ; `statut = statut_depense(...)` ;
  `date_paiement = _now()` si `montant_regle > 0` sinon `None`.
- `add_depense_reglement(conn, depense_id, versement, *, mode=None, motif=None, when=None)`
  — **remplace** l'idée de `mark_*` : lit la dépense, `nouveau = montant_regle + versement`
  (borné `]0, montant]`), met à jour `montant_regle`, `date_paiement = when or _now()`,
  `mode = COALESCE(?, mode)`, `motif = COALESCE(?, motif)`, et
  `statut = statut_depense(montant, nouveau)`. Valide `versement > 0` et `versement <= reste`.
- `list_depenses(conn, prestataire_id, limit, offset)`,
  `count_depenses_for_prestataire(conn, prestataire_id)`, `delete_depense(conn, id)`.
- Filtres globaux (calque `_paiement_filter_clause`/`list_paiements_filtered`/`count_paiements`/
  `total_paiements`, `crm/repo.py:764-869`), **joints à `prestataires`** :
  `list_depenses_filtered(conn, search="", statut="en_attente", limit=None, offset=0,
  date_from="", date_to="")` → `list[tuple[Depense, Prestataire]]`,
  `count_depenses(conn, ...)`,
  `total_depenses(conn, ...)` → renvoie un triplet de sommes utile au dashboard :
  `SUM(montant)`, `SUM(montant_regle)`, `SUM(montant - montant_regle)`.
  - Le filtre statut accepte `en_attente | regle_partiellement | regle | tous`.
  - Colonne date contextuelle (calque `crm/repo.py:792-795`) :
    `regle`/`regle_partiellement` → `date_paiement`, `en_attente` → `date_echeance`,
    sinon `created_at`.

### 2.4 Audit
Réutiliser `repo.log_audit` (`crm/repo.py:1106`). Actions :
`prestataire_cree`, `facture_importee`, `depense_creee`, `depense_reglee` (préciser
versement vs solde dans `detail`), `depense_supprimee`.

---

## 3. Couche IA — provider abstrait + factory (`src/ai/`)

Objectif architectural : **découpler la fonctionnalité du fournisseur**. Une fonctionnalité
(ex. « extraire le montant d'une facture ») déclare *quel provider* elle utilise, *quel prompt*
elle applique et *quel modèle* ; un **factory** instancie le bon provider d'après la config.
Ajouter un provider (Anthropic, OpenAI…) ou une fonctionnalité IA future = ajouter une classe /
une section de config, **sans toucher** au code appelant.

**Premier provider : Qwen-VL-OCR** (Alibaba DashScope). Implémenté en **HTTP via `requests`**
(déjà une dépendance — `src/mailer.py`), via l'endpoint **OpenAI-compatible** de DashScope
(`/compatible-mode/v1/chat/completions`, bloc `image_url`), donc **aucune nouvelle dépendance**
ni complication PyInstaller.

> ⚠️ **Les factures sont des scans.** Hypothèse métier confirmée : entrées **JPG/PNG**, ou
> **PDF contenant une image** (pas de texte sélectionnable). La fonctionnalité est donc
> **vision-only** : pas d'étape « extraction de texte » (un `get_text` PyMuPDF renverrait vide
> sur un scan). Pipeline : **image → modèle vision** ; **PDF scanné → rasterisé en image
> (PyMuPDF, ~200 DPI) → modèle vision**. Un modèle vision-LLM cloud (Qwen-VL-OCR) est aussi
> **plus robuste qu'un OCR local** sur des photos bruitées/inclinées. Grâce au factory, basculer
> vers un autre provider vision (Gemini, Anthropic, OpenAI) reste un simple changement de
> config — l'interface expose déjà `images` + `supports_vision`.

### 3.0 Arborescence
```
src/ai/
  __init__.py
  base.py            # AIProvider (ABC), ImagePart, AIError
  factory.py         # registre + build_provider + provider_for_feature
  images.py          # as_image_parts(path) : JPG/PNG direct + rasterisation PDF (PyMuPDF)
  features/
    __init__.py
    facture_montant.py   # 1re fonctionnalité : extract_facture_montant(...)
  providers/
    __init__.py
    qwen.py          # QwenVisionProvider (HTTP/requests, DashScope OpenAI-compatible)
    # gemini.py, anthropic.py … (futurs, même interface)
prompts/
  facture_montant.txt    # prompt ÉDITABLE par l'utilisateur (cf. §3.5)
```

### 3.1 Config (`config.ini` + `src/config.py`) — clés par provider, provider par fonctionnalité
`config.ini` (clés **git-ignorées** comme le reste du fichier) :
```ini
; --- Fournisseurs IA : 1 section par provider, clé d'API propre ---
[ai_provider_qwen]
api_key  = sk-...
; Endpoint OpenAI-compatible DashScope (international hors Chine).
base_url = https://dashscope-intl.aliyuncs.com/compatible-mode/v1
model    = qwen-vl-ocr

[ai_provider_gemini]         ; exemple futur (PDF natif) — laissé vide pour l'instant
api_key  =
model    = gemini-2.0-flash

; --- Fonctionnalités IA : 1 section par fonctionnalité ---
[ai_feature_facture_montant]
provider = qwen                           ; quel provider sert CETTE fonctionnalité
prompt   = prompts/facture_montant.txt    ; prompt éditable (chemin relatif à l'app)
enabled  = true
```

`src/config.py` — dataclasses + chargement générique (itère les sections `ai_provider_*` /
`ai_feature_*`, donc extensible sans recompiler la logique) :
```python
@dataclass(frozen=True)
class AIProviderCfg:
    name: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""

@dataclass(frozen=True)
class AIFeatureCfg:
    name: str
    provider: str
    prompt_path: str
    enabled: bool = True

@dataclass(frozen=True)
class AIConfig:
    providers: dict[str, AIProviderCfg]
    features: dict[str, AIFeatureCfg]
    def provider(self, name: str) -> AIProviderCfg | None: return self.providers.get(name)
    def feature(self, name: str) -> AIFeatureCfg | None: return self.features.get(name)
```
Chargement (ajouté à `load_config`, sections **optionnelles** : ne pas faire échouer si absentes) :
```python
providers, features = {}, {}
for sec in parser.sections():
    if sec.startswith("ai_provider_"):
        name = sec[len("ai_provider_"):]
        providers[name] = AIProviderCfg(
            name=name,
            api_key=parser.get(sec, "api_key", fallback=""),
            base_url=parser.get(sec, "base_url", fallback=""),
            model=parser.get(sec, "model", fallback=""))
    elif sec.startswith("ai_feature_"):
        name = sec[len("ai_feature_"):]
        features[name] = AIFeatureCfg(
            name=name,
            provider=parser.get(sec, "provider", fallback=""),
            prompt_path=parser.get(sec, "prompt", fallback=""),
            enabled=parser.getboolean(sec, "enabled", fallback=True))
ai = AIConfig(providers=providers, features=features)
```
Ajouter `ai: AIConfig` à `Config`.

### 3.2 Interface provider — `src/ai/base.py`
Deux capacités seulement, suffisantes pour toutes les fonctionnalités d'extraction :
```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

class AIError(RuntimeError):
    """Toute défaillance provider (réseau, auth, quota, réponse invalide)."""

@dataclass
class ImagePart:
    media_type: str     # image/png, image/jpeg, application/pdf
    data_b64: str

class AIProvider(ABC):
    name: str = ""
    supports_vision: bool = False          # le factory/feature s'en sert pour router

    def __init__(self, cfg: "AIProviderCfg") -> None:
        self.cfg = cfg

    @abstractmethod
    def complete_json(self, *, system: str, user: str,
                      images: list[ImagePart] | None = None,
                      max_tokens: int = 512) -> dict:
        """Renvoie un dict JSON. Lève AIError en cas d'échec."""
```

### 3.3 Provider Qwen-VL-OCR — `src/ai/providers/qwen.py`
DashScope expose un endpoint **OpenAI-compatible** : on envoie l'image dans un bloc
`image_url` (data-URL base64). On ne s'appuie **pas** sur `response_format` (support variable
sur les modèles VL) : le prompt impose le JSON et on le parse de façon tolérante.
```python
import json
import re
import requests
from ..base import AIProvider, AIError, ImagePart

_DEFAULT_BASE = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

def _data_url(p: ImagePart) -> str:
    return f"data:{p.media_type};base64,{p.data_b64}"

def _extract_json(txt: str) -> dict:
    """Tolère ```json … ``` ou du texte autour (robustesse VL/OCR)."""
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        raise AIError(f"Pas de JSON dans la réponse: {txt[:120]}")
    try:
        return json.loads(m.group(0))
    except ValueError as e:
        raise AIError(f"JSON invalide: {e}") from e

class QwenVisionProvider(AIProvider):
    name = "qwen"
    supports_vision = True

    def complete_json(self, *, system, user, images=None, max_tokens=512):
        base = (self.cfg.base_url or _DEFAULT_BASE).rstrip("/")
        content = [{"type": "text", "text": user}]
        for img in (images or []):
            content.append({"type": "image_url", "image_url": {"url": _data_url(img)}})
        try:
            r = requests.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {self.cfg.api_key}",
                         "Content-Type": "application/json"},
                json={"model": self.cfg.model or "qwen-vl-ocr",
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": content}],
                      "max_tokens": max_tokens, "stream": False},
                timeout=60)        # vision : images = payload plus lourd
        except requests.RequestException as e:
            raise AIError(f"Qwen réseau: {e}") from e
        if r.status_code != 200:
            raise AIError(f"Qwen HTTP {r.status_code}: {r.text[:200]}")
        try:
            txt = r.json()["choices"][0]["message"]["content"]
        except (KeyError, ValueError, IndexError) as e:
            raise AIError(f"Qwen réponse invalide: {e}") from e
        return _extract_json(txt)
```
> Région : `dashscope-intl.…` hors Chine (le cabinet est en Tunisie). Modèle `qwen-vl-ocr`
> (spécialisé documents) ; `qwen-vl-plus` est une alternative qui suit mieux des consignes
> complexes si besoin. Réglable via `config.ini` (`model`), sans toucher au code.

### 3.4 Factory — `src/ai/factory.py`
```python
from .base import AIProvider, AIError
from .providers.qwen import QwenVisionProvider

_REGISTRY: dict[str, type[AIProvider]] = {
    "qwen": QwenVisionProvider,
    # "gemini": GeminiProvider, "anthropic": AnthropicProvider,  # à enregistrer quand ajoutés
}

def register_provider(name: str, cls: type[AIProvider]) -> None:
    _REGISTRY[name] = cls

def build_provider(pcfg) -> AIProvider:
    cls = _REGISTRY.get(pcfg.name)
    if cls is None:
        raise AIError(f"Provider IA inconnu: {pcfg.name!r}")
    return cls(pcfg)

def provider_for_feature(cfg, feature: str) -> AIProvider | None:
    """Renvoie le provider configuré pour une fonctionnalité, ou None si IA indisponible."""
    feat = cfg.ai.feature(feature)
    if feat is None or not feat.enabled:
        return None
    pcfg = cfg.ai.provider(feat.provider)
    if pcfg is None or not pcfg.api_key.strip():
        return None
    return build_provider(pcfg)
```

### 3.5 Prompt éditable — `prompts/facture_montant.txt`
Fichier texte versionné (gabarit par défaut), **modifiable par l'utilisateur** pour changer la
façon d'extraire l'information sans toucher au code (comme `templates/` pour le Word) :
```
Tu es un assistant comptable. On te donne l'IMAGE d'une facture fournisseur scannée.
Lis-la et extrais le MONTANT TOTAL À PAYER (TTC).
Attention au format français : « 1 234,56 » signifie 1234.56 (espace = milliers,
virgule = décimale). Renvoie le montant comme un nombre à point décimal.
Réponds STRICTEMENT en json : {"montant": <nombre ou null>,
"devise": "<code ou null>", "confiance": "haute|moyenne|basse"}.
montant=null si tu ne le trouves pas. N'invente jamais de valeur.
```
> Le prompt n'est volontairement **pas** en dur dans le code. Une future fonctionnalité IA
> aura son propre fichier `prompts/<feature>.txt` + sa section `[ai_feature_<feature>]`.

### 3.6 Image(s) en entrée — `src/ai/images.py`
Convertit l'entrée (JPG/PNG **ou** PDF scanné) en `ImagePart`(s). Le PDF est **rasterisé** par
PyMuPDF (déjà présent) à ~200 DPI ; on borne le nombre de pages (le total est en page 1/2).
```python
import base64
from pathlib import Path
from .base import ImagePart, AIError

_DPI_ZOOM = 200 / 72        # ~200 DPI (matrice de zoom PyMuPDF)
_MAX_PAGES = 2              # le total figure quasi toujours en page 1 ou 2

def as_image_parts(path: Path, *, max_pages: int = _MAX_PAGES) -> list[ImagePart]:
    suf = path.suffix.lower()
    if suf in (".jpg", ".jpeg", ".png"):
        media = "image/png" if suf == ".png" else "image/jpeg"
        b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        return [ImagePart(media_type=media, data_b64=b64)]
    if suf == ".pdf":
        import fitz                              # PyMuPDF (cf. src/pdf_to_jpg.py)
        parts: list[ImagePart] = []
        mat = fitz.Matrix(_DPI_ZOOM, _DPI_ZOOM)
        with fitz.open(path) as doc:
            for page in list(doc)[:max_pages]:
                pix = page.get_pixmap(matrix=mat)          # rendu raster
                b64 = base64.standard_b64encode(pix.tobytes("jpeg")).decode("ascii")
                parts.append(ImagePart(media_type="image/jpeg", data_b64=b64))
        if not parts:
            raise AIError("PDF sans page exploitable.")
        return parts
    raise AIError(f"Format non supporté: {suf}")
```

### 3.7 Fonctionnalité 1 (vision-only) — `src/ai/features/facture_montant.py`
```python
from pathlib import Path
from ..factory import provider_for_feature
from ..base import AIError
from ..images import as_image_parts
from ...config import app_dir          # résolution du chemin de prompt (cf. crm/db.py:app_dir)

FEATURE = "facture_montant"

def _parse_montant(v) -> float | None:
    try:
        return float(v) if v is not None else None      # le provider renvoie déjà un nombre
    except (TypeError, ValueError):
        return None

def extract_facture_montant(cfg, src_path) -> float | None:
    """Montant TTC lu sur le scan, ou None (IA off / format inconnu / échec). Ne lève jamais."""
    provider = provider_for_feature(cfg, FEATURE)
    if provider is None or not provider.supports_vision:    # cette feature exige la vision
        return None
    feat = cfg.ai.feature(FEATURE)
    try:
        system = (app_dir() / feat.prompt_path).read_text(encoding="utf-8")
        images = as_image_parts(Path(src_path))             # JPG/PNG direct, PDF → rasterisé
        data = provider.complete_json(
            system=system, user="Facture scannée en pièce jointe.",
            images=images, max_tokens=256)
        return _parse_montant(data.get("montant"))
    except (AIError, OSError):
        return None
```

> **Garanties** : un seul point d'appel côté app (`extract_facture_montant(cfg, path)`) ;
> jamais d'exception remontée ; **le montant pré-remplit un champ éditable, jamais auto-validé**
> (filet contre une mauvaise lecture OCR) ; appel **dans le thread d'arrière-plan** (`_run_busy`)
> car bloquant (réseau).

---

## 4. Import/archivage — `crm/generator.py`

Le moteur patient (`save_draft`/`render_document`/`send_document`) **n'est pas modifié**. On
ajoute un chemin d'import sans Word ni Mailjet.

### 4.1 Dossier prestataire (calque `patient_dir`, `crm/generator.py:39`)
```python
def prestataire_dir(p: Prestataire) -> Path:
    parts = [_slug(p.nom), _slug(p.prenom)]
    name = "_".join(s for s in parts if s) or f"prestataire_{p.id}"
    d = output_dir() / "prestataires" / name
    d.mkdir(parents=True, exist_ok=True)
    return d
```

### 4.2 `import_facture`
```python
def import_facture(conn, prestataire, src_path, *, montant=None,
                   libelle=None, doc_id=None) -> Facture:
    """Archive le fichier uploadé et crée la ligne `factures`. Pas de Word, pas d'envoi."""
    src = Path(src_path)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")          # nom horodaté = unicité
    ext = src.suffix.lower()
    dest = prestataire_dir(prestataire) / f"facture_{stamp}{ext}"
    shutil.copy2(src, dest)                                     # import os/shutil à ajouter
    fac = Facture(id=None, prestataire_id=prestataire.id, fichier=str(dest),
                  nom_original=src.name, montant=montant, libelle=libelle)
    return repo.create_facture(conn, fac)
```
- `ai.features.facture_montant.extract_facture_montant(cfg, path)` (§3.6) est appelé **par
  l'app** avant `import_facture`, pour pré-remplir le champ montant ; `import_facture` reçoit le
  montant déjà résolu (IA ou manuel).
- **Idempotence** : le nom horodaté évite toute collision (entre imports et avec les patients,
  dossier dédié `output/prestataires/`).

### 4.3 Suppression
À la suppression d'une facture/dépense côté app : `repo.delete_facture` puis `Path(fichier).unlink(missing_ok=True)`
(best-effort). `ON DELETE SET NULL` sur `depenses.facture_id` évite les orphelins bloquants.

---

## 5. UI — `crm/app.py`

### 5.1 Libellés & couleurs (haut de fichier, près de `crm/app.py:43,73`)
```python
_DEPENSE_STATUT_LABELS = {
    "en_attente":         ("À régler",            NAVY),
    "regle_partiellement":("Réglé partiellement", AMBER),
    "regle":              ("Réglé",               GREEN),
}
```
`_MODE_LABELS` (`crm/app.py:73`) réutilisé tel quel pour le mode de règlement.

### 5.2 Rail (`_build_shell`, `crm/app.py:325-403`)
6 entrées : `Tableau · Patients · Prestataires · Finances · Travaux · Paramétrage`.
Icône Prestataires `STOREFRONT`. « Paiements » → **Finances** avec sous-menu
Paiements / Dépenses (calque `_travaux_submenu`/`_param_submenu`,
`crm/app.py:2011,1737`). Étendre `SC_NAV` (`crm/app.py:177`) à 6 vues et l'état
`current_view` (`crm/app.py:193`) aux valeurs `prestataires` / `depenses`.

### 5.3 Vues & raccourcis
Étendre `_reset_and`, `_page_step`, `_focus_search`, `_new_for_current_view`
(`crm/app.py:543-626`) pour `prestataires` (Nouveau = dialog prestataire) et `depenses`.
Champs de recherche/état paginés dédiés (calque du bloc « Patients », `crm/app.py:201-204`).

### 5.4 Page Prestataires (calque `show_patients` `crm/app.py:964` + `_patient_dialog` `crm/app.py:2293`)
- Liste paginée + recherche + bouton « Nouveau prestataire ».
- Dialog création/édition : nom, prénom, adresse (multiline), email, téléphone ;
  détection doublon via `find_prestataire_matches` (réutiliser le bandeau d'homonymes de
  `_patient_dialog`).
- Fiche prestataire (calque `show_patient_detail` `crm/app.py:1329`) : 2 sections paginées
  **Factures** (`list_factures`, ouverture du fichier via `os.startfile`/`open_in_word`
  pattern de `crm/templates.py:81`) et **Dépenses** (`list_depenses`), + bouton
  **« Importer une facture »**.

### 5.5 Dialog d'import (nouveau ; PAS de calque `_generate_dialog`)
Composants Flet : `ft.FilePicker` (sélection PDF/image) + champs.
Séquence à l'ouverture / sélection de fichier :
1. `FilePicker` → chemin local.
2. Case **« Extraire le montant automatiquement »** (cochée par défaut ; désactivée si
   `ai.factory.provider_for_feature(cfg, "facture_montant") is None` — IA indisponible/non
   configurée). Si cochée : dans `_run_busy`,
   `ai.features.facture_montant.extract_facture_montant(cfg, path)` → pré-remplit le champ
   **montant total** (éditable). `None` (échec / scanné sans texte / décoché) → saisie manuelle.
3. Case **« Ajouter une ligne de dépense »** (cochée) + **montant total** + **échéance**
   (`_date_field`, `crm/app.py:698`).
4. **Part déjà payée** (optionnelle) : toggle **% / montant** + champ valeur + **motif**.
   Conversion : si mode %, `paye = round(montant * pct/100, 2)` ; borne `0 ≤ paye ≤ montant`.
5. Validation (dans `_run_busy`, thread d'arrière-plan) :
   ```
   fac = generator.import_facture(conn, prestataire, path, montant=montant, libelle=libelle)
   if ajouter_depense and montant > 0:
       repo.create_depense(conn, prestataire.id, montant,
                           montant_regle=paye, motif=motif, facture_id=fac.id,
                           date_echeance=echeance)
   log_audit('facture_importee', …) ; log_audit('depense_creee', …)
   ```

### 5.6 Page Finances → onglet Dépenses (calque `show_paiements`/`_refresh_paiements` `crm/app.py:1609`)
- Filtres : recherche prestataire, statut (`en_attente`/`regle_partiellement`/`regle`/`tous`),
  période (`_date_field`).
- Carte récap (calque `paie_summary`) : **total dû / total réglé / reste à payer** via
  `total_depenses(...)`.
- Lignes : total dû, réglé, **reste**, prestataire, échéance/dernier règlement, **chip** statut
  (`_DEPENSE_STATUT_LABELS`), pagination `_pagination` (`crm/app.py:633`).
- Actions : **Régler** (`CHECK_CIRCLE`), **Supprimer** (`DELETE`), **Ouvrir fiche**.

### 5.7 Modales Régler / Supprimer
- **Régler** (calque `_encaisser` `crm/app.py:2702`) : affiche total dû / déjà réglé / **reste** ;
  champ **versement** (défaut = reste, borné `]0, reste]`), dropdown **mode** (`_MODE_LABELS`),
  **motif** optionnel → `repo.add_depense_reglement(conn, dep.id, versement, mode=…, motif=…)`
  + `log_audit('depense_reglee', …)`.
- **Supprimer** (calque `_annuler_paiement` `crm/app.py:2748`) → `repo.delete_depense` (+ suppression
  du fichier de la facture liée si plus aucune dépense ne la référence) + `log_audit`.

### 5.8 Travaux & Paramétrage : inchangés
Travaux reste **patient pur** ; aucun filtre `partie`, aucun job pour les factures.
Paramétrage : pas de typage de modèles. (PRD §6.6, §3.3.)

### 5.9 Tableau de bord (calque `_refresh_dashboard` `crm/app.py:889`, `_camembert` `crm/app.py:845`)
- KPI : **Dépenses réglées**, **Reste à payer**, **Solde net** (encaissé − réglé) via
  `total_paiements(...)` (existant) et `total_depenses(...)` (nouveau).
- Graphe balance entrées/sorties : nouveau canvas calqué sur `_camembert`, **sans dépendance
  ajoutée** (Flet + PyMuPDF). Légende Entrées (vert) / Sorties (ambre/rouge) + solde.

---

## 6. Règles métier (récap calculs)

| Calcul | Formule |
|---|---|
| Reste à payer | `max(0, montant − montant_regle)` (dérivé, non stocké) |
| Statut | `statut_depense(montant, montant_regle)` (§2.3) |
| % → montant (avance) | `round(montant * pct / 100, 2)`, borné `[0, montant]` |
| Versement valide | `0 < versement ≤ reste` |
| Solde net dashboard | `Σ paiements encaissés − Σ depenses.montant_regle` |

---

## 7. Dépendances & build

- **Aucune nouvelle dépendance** pour Qwen-VL-OCR : le provider utilise `requests` (déjà dans
  `requirements.txt`) et `fitz`/PyMuPDF (déjà présent) pour rasteriser les PDF. Rien à ajouter.
- **PyInstaller** (`crm-desktop.spec`, `crm-web.spec`) : aucun `hiddenimports` supplémentaire
  (requests/PyMuPDF déjà embarqués). Veiller seulement à inclure le dossier **`prompts/`**
  dans les `datas` du build (comme `templates/`/`config.ini`).
- `config.ini` (copié près de l'exe au build) : ajouter les sections `[ai_provider_qwen]`
  et `[ai_feature_facture_montant]` (clé vide ⇒ IA désactivée). Reste **git-ignoré**.
- Tester l'exe gelé **hors-ligne** : l'app démarre et l'import fonctionne sans IA (clé absente
  ⇒ `provider_for_feature` renvoie `None` ⇒ saisie manuelle).
- **Provider futur (Gemini/OpenAI/Anthropic)** : si ajouté avec un SDK dédié, intégrer alors
  ses `hiddenimports`. Tant qu'on reste sur des providers HTTP (Qwen via `requests`), le build
  est inchangé.

---

## 8. Préservation des données (rappel, voir PRD §9)

1. Migration **purement additive** : `prestataires`, `factures`, `depenses` via
   `CREATE TABLE IF NOT EXISTS`. **`documents` jamais modifiée** ⇒ risque quasi nul.
2. `SCHEMA_VERSION` 5 → 6 ; `_migrate` inchangé (aucun `ALTER`).
3. Snapshot pré-migration déjà pris avant `_migrate` (filet conservé).
4. Anti-downgrade actif (`SchemaTooNewError`).
5. Aucune opération destructive hors `crm.reset`. (À étendre : `crm/reset.py` doit aussi
   vider `prestataires`/`factures`/`depenses` et `output/prestataires/`.)
6. Idempotence fichiers : factures dans `output/prestataires/<slug>/`, noms horodatés.

---

## 9. Plan de tests (manuel, Windows + Word ; IA = réseau)

1. **Migration** : copier un `cabinet.db` de prod (depuis `backups/`), lancer
   `python crm_app.py` → vérifier `meta.schema_version=6`, snapshot
   `cabinet-v5-to-v6-*.db` créé, patients/documents/paiements **intacts**, nouvelles tables
   vides.
2. **Prestataire** : créer, déclencher un doublon (même nom/prénom), éditer.
3. **Import + IA (vision)** : importer une **facture scannée** — JPG/PNG, puis un **PDF
   contenant une image** (vérifier la rasterisation PyMuPDF → image). Case IA cochée
   (`[ai_provider_qwen].api_key` renseignée) → montant pré-rempli ; vérifier la lecture du
   **format FR** (« 1 234,56 » → 1234.56). Décocher → saisie manuelle ; clé vide → case grisée ;
   format inconnu/échec réseau → repli manuel sans planter.
   Vérifier l'archivage dans `output/prestataires/<slug>/facture_<stamp>.pdf`, la ligne
   `factures` et la ligne `depenses` (avance % puis montant + motif → statut
   `regle_partiellement`).
4. **Règlements** : régler partiellement (reste recalculé) puis solder → statut `regle`,
   `date_paiement`/`mode` à jour ; supprimer une dépense (+ fichier nettoyé).
5. **Finances** : filtres statut/période/recherche ; carte récap (dû/réglé/reste) ;
   pagination > 1 page.
6. **Dashboard** : KPI dépenses + graphe balance cohérents avec les données.
7. **Build gelé hors-ligne** : l'app démarre, l'import marche sans IA, aucune erreur d'import
   `anthropic`/`pydantic_core`.

---

## 10. Fichiers touchés

| Fichier | Changement |
|---|---|
| `crm/db.py` | `SCHEMA_VERSION=6` ; 3 tables dans `_SCHEMA` (additif). `_migrate` inchangé. |
| `crm/repo.py` | Dataclasses + CRUD `Prestataire` / `Facture` / `Depense` (+ `statut_depense`, `add_depense_reglement`). |
| `src/ai/` (package) | **Nouveau** : `base.py` (ABC `AIProvider`), `factory.py` (registre + `provider_for_feature`), `images.py` (JPG/PNG + rasterisation PDF/PyMuPDF), `providers/qwen.py`, `features/facture_montant.py`. |
| `prompts/facture_montant.txt` | **Nouveau** : prompt éditable de la 1re fonctionnalité. |
| `src/config.py` | Dataclasses `AIProviderCfg`/`AIFeatureCfg`/`AIConfig` + chargement des sections `ai_provider_*` / `ai_feature_*` (optionnelles). |
| `crm/generator.py` | `prestataire_dir`, `import_facture` (archivage, sans Word/Mailjet). |
| `crm/app.py` | Rail 6 entrées, page Prestataires + fiche, dialog import+dépense, Finances/Dépenses, modales régler/supprimer, dashboard. |
| `crm/reset.py` | Vider les nouvelles tables + `output/prestataires/`. |
| `requirements.txt` | **Inchangé** (Qwen via `requests` + rasterisation PyMuPDF déjà présents). |
| `crm-desktop.spec` / `crm-web.spec` | Ajouter `prompts/` aux `datas`. (Pas de `hiddenimports` tant qu'on reste sur des providers HTTP.) |
| `config.ini` | Sections `[ai_provider_qwen]` + `[ai_feature_facture_montant]` (clé vide, git-ignoré). |

> Non modifiés : `documents`, `crm/templates.py`, `src/doc_filler.py`, `src/mailer.py`,
> `src/pdf_to_jpg.py`.
