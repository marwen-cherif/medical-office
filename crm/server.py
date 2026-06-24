"""Backend de services (sidecar) de l'UI React — facade HTTP localhost.

Ce module expose une **facade de services** FastAPI : une opération par cas d'usage
de l'interface, qui **reutilise le moteur existant** (`src/` + `crm/` hors `app.py`)
**sans modifier ses signatures publiques**. Aucune regle metier n'est reimplementee
ici : les routes ne font qu'appeler `crm/repo.py`, `crm/templates.py`,
`crm/printing.py`, etc. et serialiser le resultat en JSON.

Perimetre de cet increment (walking skeleton) : l'ecran **Parametrage** (modeles de
documents, modeles d'email, imprimante, catalogue d'actes). Les autres ecrans
(Patients, Finances, ...) seront ajoutes par increments ulterieurs.

Invariants preserves (cf. CLAUDE.md), tous portes par le backend Python inchange :
  - Windows + Word COM pour la generation (hors perimetre du pilote, mais la
    dependance n'est pas retiree) ;
  - donnees **a cote de l'exe** (`data/`, `output/`, `templates/`, `config.ini`)
    via `crm/db.app_dir()` ;
  - **backup pre-migration** (`backup.backup_db`) PUIS `db.connect` (migrations +
    garde anti-downgrade `SchemaTooNewError`) au demarrage ;
  - idempotence par nom de fichier (`crm/generator.build_filename`) ;
  - secrets `config.ini` (cles Mailjet) **jamais** exposes : ce module ne lit meme
    pas la configuration — aucune cle ne peut donc transiter vers le frontend.

Transport (cf. design D3) : HTTP sur **127.0.0.1**, **port ephemere** choisi au
demarrage, **jeton de session** exige sur toutes les routes `/api/*`. Le port et le
jeton sont transmis a la coquille (Tauri) via une ligne de handshake sur stdout
(`CRM_SERVER_READY {json}`), lue au lancement.

Lancement direct (dev) :
    python -m crm.server --port 0           # port ephemere, jeton auto
    python -m crm.server --port 8765 --token dev   # fixe (pratique pour Vite)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import socket
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import backup, print_settings, printing, repo, templates, version
from .db import SchemaTooNewError, connect

# Ligne de handshake imprimee sur stdout au demarrage : la coquille Tauri y lit le
# port effectif et le jeton de session (cf. design D5 / Open Questions).
HANDSHAKE_PREFIX = "CRM_SERVER_READY "

# Cle `meta` de l'imprimante cible (identique a crm/app.py : base partagee).
PRINTER_KEY = "printer_name"


# =============================================================================
# Erreurs structurees (codes stables -> presentation FR cote frontend)
# =============================================================================

class ApiError(Exception):
    """Erreur metier traduite en reponse JSON `{error: {code, message}}`.

    `code` est un identifiant **stable** que le frontend mappe vers un message
    francais (cf. tache 3.5). `status` est le code HTTP associe.
    """

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


# Codes d'erreur du contrat (cf. tasks 1.6). Le frontend les traduit en FR.
ERR_WORD_UNAVAILABLE = "WORD_UNAVAILABLE"
ERR_PRINTER_NOT_FOUND = "PRINTER_NOT_FOUND"
ERR_PRINT_FAILED = "PRINT_FAILED"
ERR_TEMPLATE_INVALID = "TEMPLATE_INVALID"
ERR_TEMPLATE_EXISTS = "TEMPLATE_EXISTS"
ERR_NOT_FOUND = "NOT_FOUND"
ERR_SCHEMA_TOO_NEW = "SCHEMA_TOO_NEW"
ERR_VALIDATION = "VALIDATION_ERROR"


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# =============================================================================
# Gestionnaire d'operations longues (jobs in-memory) + canal SSE
# =============================================================================

class JobManager:
    """Suivi en memoire des operations longues, diffusees en SSE.

    Pour le pilote, les operations longues sont le **test d'impression** et (a
    terme) la generation/envoi. Chaque job possede une file d'evenements
    asyncio ; le frontend s'y abonne via `GET /api/events/{job_id}`. La
    persistance dans la table `jobs` (`repo.create_job`/...) reste disponible
    pour les traitements par lot ; un test d'impression ponctuel n'a pas a la
    polluer, on le garde donc en memoire.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
        self._final: dict[str, dict] = {}  # dernier evenement (pour abonnement tardif)
        self._lock = threading.Lock()

    def create(self) -> str:
        job_id = secrets.token_urlsafe(8)
        with self._lock:
            self._queues[job_id] = asyncio.Queue()
        return job_id

    def _publish(self, job_id: str, event: dict) -> None:
        """Depose un evenement (thread-safe vis-a-vis de la boucle asyncio)."""
        q = self._queues.get(job_id)
        if q is None:
            return
        if event.get("type") in ("done", "error"):
            self._final[job_id] = event
        loop = STATE.loop
        if loop is not None:
            loop.call_soon_threadsafe(q.put_nowait, event)
        else:  # pragma: no cover - hors boucle (ne devrait pas arriver)
            q.put_nowait(event)

    def progress(self, job_id: str, value: float, message: str = "") -> None:
        self._publish(job_id, {"type": "progress", "value": value, "message": message})

    def done(self, job_id: str, result: Any = None) -> None:
        self._publish(job_id, {"type": "done", "result": result})

    def error(self, job_id: str, code: str, message: str) -> None:
        self._publish(job_id, {"type": "error", "code": code, "message": message})

    async def stream(self, job_id: str):
        """Generateur SSE : yield les evenements d'un job jusqu'a done/error."""
        q = self._queues.get(job_id)
        if q is None:
            # Job inconnu (ou deja purge) : on renvoie l'eventuel etat final connu.
            final = self._final.get(job_id)
            if final is not None:
                yield _sse(final)
            else:
                yield _sse({"type": "error", "code": ERR_NOT_FOUND,
                            "message": "Tâche inconnue."})
            return
        try:
            while True:
                event = await q.get()
                yield _sse(event)
                if event.get("type") in ("done", "error"):
                    break
        finally:
            with self._lock:
                self._queues.pop(job_id, None)


def _sse(event: dict) -> str:
    """Formate un evenement au format Server-Sent Events."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# =============================================================================
# Etat applicatif partage (connexion SQLite unique + verrou)
# =============================================================================

class AppState:
    """Connexion SQLite unique partagee, protegee par un verrou.

    Calque le modele de `crm/app.py` (une connexion `check_same_thread=False`,
    acces serialise). Les handlers FastAPI synchrones s'executent dans un
    threadpool : le verrou garantit qu'un seul acces base a lieu a la fois, ce
    qui evite tout conflit d'ecriture concurrent sur SQLite.
    """

    def __init__(self) -> None:
        self.conn = None  # type: ignore[assignment]
        self.db_lock = threading.Lock()
        self.token: str = ""
        # Operations longues serialisees dans un unique thread worker (COM initialise
        # dans ce thread, jamais dans la boucle ASGI — cf. design R4).
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="crm-job")
        self.jobs = JobManager()
        self.loop: Optional[asyncio.AbstractEventLoop] = None


STATE = AppState()


def get_conn():
    """Connexion SQLite partagee (levee si le backend n'est pas initialise)."""
    if STATE.conn is None:
        raise ApiError("NOT_READY", "Base de donnees non initialisee.", status=503)
    return STATE.conn


class _Db:
    """Context manager : prend le verrou base pour la duree d'un bloc d'acces."""

    def __enter__(self):
        STATE.db_lock.acquire()
        return get_conn()

    def __exit__(self, *exc):
        STATE.db_lock.release()
        return False


def db() -> _Db:
    return _Db()


# =============================================================================
# Operations longues : execution dans le worker serialise
# =============================================================================

def _run_job(job_id: str, fn: Callable[[Callable[[float, str], None]], Any]) -> None:
    """Execute `fn` dans le thread worker (COM initialise), publie le resultat.

    `fn` recoit un callback `report(value, message)` pour la progression.
    """
    # Initialisation COM dans le thread worker (necessaire pour Word ; inoffensif
    # pour l'impression GDI). Ne jamais initialiser COM dans la boucle ASGI (R4).
    com_ready = False
    if os.name == "nt":
        try:
            import pythoncom  # type: ignore
            pythoncom.CoInitialize()
            com_ready = True
        except Exception:  # noqa: BLE001
            com_ready = False
    try:
        def report(value: float, message: str = "") -> None:
            STATE.jobs.progress(job_id, value, message)

        result = fn(report)
        STATE.jobs.done(job_id, result)
    except ApiError as exc:
        STATE.jobs.error(job_id, exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001
        STATE.jobs.error(job_id, ERR_PRINT_FAILED, str(exc))
    finally:
        if com_ready:
            try:
                import pythoncom  # type: ignore
                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass


def submit_job(fn: Callable[[Callable[[float, str], None]], Any]) -> str:
    """Cree un job, le planifie dans le worker serialise, renvoie son identifiant."""
    job_id = STATE.jobs.create()
    STATE.executor.submit(_run_job, job_id, fn)
    return job_id


# =============================================================================
# Modeles (Pydantic) — contrat OpenAPI consomme par le client TypeScript
# =============================================================================

class TemplateOut(BaseModel):
    name: str
    label: str
    categorie: Optional[str] = None
    is_multiligne: bool = False
    document_tags: list[str] = Field(default_factory=list)
    line_tags: list[str] = Field(default_factory=list)


class TemplateCreateIn(BaseModel):
    name: str


class TemplateRenameIn(BaseModel):
    new_name: str


class TemplateCategoryIn(BaseModel):
    categorie: Optional[str] = None


class PlaceholdersOut(BaseModel):
    document_tags: list[str]
    line_tags: list[str]
    auto_tags: list[str]   # remplies depuis le patient (NOM, PRENOM, ...)
    custom_tags: list[str]  # a configurer / saisir


class FieldIn(BaseModel):
    tag: str
    label: str = ""
    type: str = "text"
    default_value: str = ""


class FieldOut(FieldIn):
    pass


class CategoryOut(BaseModel):
    nom: str
    couleur: Optional[str] = None
    icone: Optional[str] = None
    sort_order: int = 0


class CategoryUpsertIn(BaseModel):
    couleur: Optional[str] = None
    icone: Optional[str] = None
    sort_order: int = 0


class CategoryRenameIn(BaseModel):
    ancien: str
    nouveau: str
    reclasser_documents: bool = False


class MailTemplateIn(BaseModel):
    name: str
    mailjet_template_id: int
    is_default: bool = False


class MailTemplateOut(MailTemplateIn):
    id: int


class PrintersOut(BaseModel):
    printers: list[str]
    default: Optional[str] = None
    selected: Optional[str] = None


class PrinterSelectIn(BaseModel):
    printer_name: str


class PrinterTestIn(BaseModel):
    printer_name: str


class PrintConfigIn(BaseModel):
    paper: Optional[str] = None
    color: Optional[str] = None


class PrintConfigOut(PrintConfigIn):
    pass


class PrintTypesOut(BaseModel):
    types: list[str]
    settings: dict[str, Any]


class CategoryValueOut(BaseModel):
    categorie: Optional[str] = None


class ActeIn(BaseModel):
    libelle: str
    prix: float = 0.0
    code: Optional[str] = None
    sort_order: int = 0


class ActeOut(ActeIn):
    id: int
    actif: bool = True


class ActeListOut(BaseModel):
    items: list[ActeOut]
    total: int


class ActeActiveIn(BaseModel):
    actif: bool


class JobAcceptedOut(BaseModel):
    job_id: str


class OkOut(BaseModel):
    ok: bool = True


class HealthOut(BaseModel):
    status: str
    version: str
    build: str
    schema_version: int


# =============================================================================
# Application FastAPI
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # La boucle asyncio sert au pont thread worker -> SSE.
    STATE.loop = asyncio.get_running_loop()
    yield
    STATE.executor.shutdown(wait=False)


app = FastAPI(
    title="Cabinet CRM — façade de services",
    version=version.__version__,
    description=(
        "Façade HTTP localhost réutilisant le moteur Python du CRM. "
        "Toutes les routes /api/* exigent l'en-tête Authorization: Bearer <jeton>."
    ),
    lifespan=lifespan,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)

# Loopback uniquement + jeton : CORS permissif sans credentials (Authorization,
# pas de cookie). Permet a Vite (dev) et a la WebView Tauri d'appeler le backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Rejette toute requete `/api/*` sans le jeton de session attendu.

    Laisse passer : preflight CORS (OPTIONS), `/openapi.json`, `/docs`, `/redoc`
    (confort de dev sur loopback). Le contrat metier vit sous `/api`.
    """
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api"):
        return await call_next(request)
    auth = request.headers.get("authorization", "")
    expected = f"Bearer {STATE.token}"
    if not STATE.token or auth != expected:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "UNAUTHORIZED",
                               "message": "Jeton de session manquant ou invalide."}},
        )
    return await call_next(request)


@app.exception_handler(ApiError)
async def _api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


def _err_from_engine(exc: Exception) -> ApiError:
    """Traduit une exception du moteur en `ApiError` a code stable."""
    if isinstance(exc, SchemaTooNewError):
        return ApiError(ERR_SCHEMA_TOO_NEW, str(exc), status=409)
    if isinstance(exc, FileExistsError):
        return ApiError(ERR_TEMPLATE_EXISTS, str(exc), status=409)
    if isinstance(exc, FileNotFoundError):
        return ApiError(ERR_NOT_FOUND, str(exc), status=404)
    if isinstance(exc, ValueError):
        return ApiError(ERR_VALIDATION, str(exc), status=400)
    return ApiError(ERR_VALIDATION, str(exc), status=400)


# --- Health -------------------------------------------------------------------

@app.get("/api/health", response_model=HealthOut, tags=["health"])
def health() -> HealthOut:
    from .db import SCHEMA_VERSION
    return HealthOut(
        status="ok",
        version=version.__version__,
        build=version.build_tag(),
        schema_version=SCHEMA_VERSION,
    )


# --- templates.* --------------------------------------------------------------

def _template_to_out(conn, t: templates.Template) -> TemplateOut:
    from src.doc_filler import classify_placeholders
    try:
        doc_tags, line_tags = classify_placeholders(t.path)
    except Exception:  # noqa: BLE001 -- .docx illisible : on n'empeche pas la liste
        doc_tags, line_tags = [], []
    return TemplateOut(
        name=t.name,
        label=t.label,
        categorie=repo.get_template_category(conn, t.name),
        is_multiligne=bool(line_tags),
        document_tags=doc_tags,
        line_tags=line_tags,
    )


@app.get("/api/templates", response_model=list[TemplateOut], tags=["templates"])
def templates_list() -> list[TemplateOut]:
    with db() as conn:
        return [_template_to_out(conn, t) for t in templates.list_templates()]


@app.post("/api/templates", response_model=TemplateOut, tags=["templates"])
def templates_create(body: TemplateCreateIn) -> TemplateOut:
    try:
        t = templates.create_template(body.name)
    except Exception as exc:  # noqa: BLE001
        raise _err_from_engine(exc)
    with db() as conn:
        return _template_to_out(conn, t)


@app.post("/api/templates/{name}/rename", response_model=TemplateOut, tags=["templates"])
def templates_rename(name: str, body: TemplateRenameIn) -> TemplateOut:
    t = templates.get_template(name)
    if t is None:
        raise ApiError(ERR_NOT_FOUND, f"Modèle introuvable : {name}", status=404)
    try:
        renamed = templates.rename_template(t, body.new_name)
    except Exception as exc:  # noqa: BLE001
        raise _err_from_engine(exc)
    with db() as conn:
        repo.rename_template_meta(conn, name, renamed.name)
        return _template_to_out(conn, renamed)


@app.delete("/api/templates/{name}", response_model=OkOut, tags=["templates"])
def templates_delete(name: str) -> OkOut:
    t = templates.get_template(name)
    if t is None:
        raise ApiError(ERR_NOT_FOUND, f"Modèle introuvable : {name}", status=404)
    templates.delete_template(t)
    with db() as conn:
        # Dissocie la categorie du modele supprime (sinon ligne orpheline).
        repo.set_template_category(conn, name, None)
    return OkOut()


@app.post("/api/templates/{name}/open-in-word", response_model=OkOut, tags=["templates"])
def templates_open_in_word(name: str) -> OkOut:
    t = templates.get_template(name)
    if t is None:
        raise ApiError(ERR_NOT_FOUND, f"Modèle introuvable : {name}", status=404)
    try:
        templates.open_in_word(t)
    except Exception as exc:  # noqa: BLE001
        raise ApiError(ERR_WORD_UNAVAILABLE,
                       f"Impossible d'ouvrir le modèle dans Word : {exc}", status=500)
    return OkOut()


@app.get("/api/templates/{name}/placeholders", response_model=PlaceholdersOut,
         tags=["templates"])
def templates_placeholders(name: str) -> PlaceholdersOut:
    from src.doc_filler import classify_placeholders
    from .generator import AUTO_PATIENT_TAGS
    t = templates.get_template(name)
    if t is None:
        raise ApiError(ERR_NOT_FOUND, f"Modèle introuvable : {name}", status=404)
    try:
        doc_tags, line_tags = classify_placeholders(t.path)
    except Exception as exc:  # noqa: BLE001
        raise ApiError(ERR_TEMPLATE_INVALID, f"Modèle illisible : {exc}", status=400)
    auto = [tag for tag in doc_tags if tag in AUTO_PATIENT_TAGS]
    custom = [tag for tag in doc_tags if tag not in AUTO_PATIENT_TAGS]
    return PlaceholdersOut(document_tags=doc_tags, line_tags=line_tags,
                           auto_tags=auto, custom_tags=custom)


@app.get("/api/templates/{name}/fields", response_model=list[FieldOut], tags=["templates"])
def templates_fields(name: str) -> list[FieldOut]:
    with db() as conn:
        return [
            FieldOut(tag=f.tag, label=f.label, type=f.type, default_value=f.default_value)
            for f in repo.list_template_fields(conn, name)
        ]


@app.put("/api/templates/{name}/fields", response_model=list[FieldOut], tags=["templates"])
def templates_set_fields(name: str, body: list[FieldIn]) -> list[FieldOut]:
    fields = [
        repo.TemplateField(template_name=name, tag=f.tag, label=f.label,
                           type=f.type, default_value=f.default_value)
        for f in body
    ]
    with db() as conn:
        repo.replace_template_fields(conn, name, fields)
        return [
            FieldOut(tag=f.tag, label=f.label, type=f.type, default_value=f.default_value)
            for f in repo.list_template_fields(conn, name)
        ]


@app.get("/api/templates/{name}/category", response_model=CategoryValueOut,
         tags=["templates"])
def templates_get_category(name: str) -> CategoryValueOut:
    with db() as conn:
        return CategoryValueOut(categorie=repo.get_template_category(conn, name))


@app.put("/api/templates/{name}/category", response_model=OkOut, tags=["templates"])
def templates_set_category(name: str, body: TemplateCategoryIn) -> OkOut:
    with db() as conn:
        repo.set_template_category(conn, name, body.categorie)
    return OkOut()


# --- categories.* -------------------------------------------------------------

@app.get("/api/categories", response_model=list[CategoryOut], tags=["categories"])
def categories_list() -> list[CategoryOut]:
    with db() as conn:
        return [
            CategoryOut(nom=c.nom, couleur=c.couleur, icone=c.icone,
                        sort_order=c.sort_order)
            for c in repo.list_categories(conn)
        ]


@app.put("/api/categories/{nom}", response_model=CategoryOut, tags=["categories"])
def categories_upsert(nom: str, body: CategoryUpsertIn) -> CategoryOut:
    try:
        with db() as conn:
            c = repo.upsert_category(conn, repo.Category(
                nom=nom, couleur=body.couleur, icone=body.icone,
                sort_order=body.sort_order))
        return CategoryOut(nom=c.nom, couleur=c.couleur, icone=c.icone,
                           sort_order=c.sort_order)
    except Exception as exc:  # noqa: BLE001
        raise _err_from_engine(exc)


@app.post("/api/categories/rename", response_model=OkOut, tags=["categories"])
def categories_rename(body: CategoryRenameIn) -> OkOut:
    from . import generator
    try:
        with db() as conn:
            reclasses = repo.rename_category(
                conn, body.ancien, body.nouveau,
                reclasser_documents=body.reclasser_documents)
            if body.reclasser_documents and reclasses:
                # Deplacement des fichiers HORS transaction (cf. repo.rename_category).
                generator.move_documents_to_category(conn, reclasses, body.nouveau)
    except Exception as exc:  # noqa: BLE001
        raise _err_from_engine(exc)
    return OkOut()


# --- mailTemplates.* ----------------------------------------------------------

@app.get("/api/mail-templates", response_model=list[MailTemplateOut], tags=["mailTemplates"])
def mail_templates_list() -> list[MailTemplateOut]:
    with db() as conn:
        return [
            MailTemplateOut(id=m.id, name=m.name,
                            mailjet_template_id=m.mailjet_template_id,
                            is_default=m.is_default)
            for m in repo.list_mail_templates(conn)
        ]


@app.post("/api/mail-templates", response_model=MailTemplateOut, tags=["mailTemplates"])
def mail_templates_create(body: MailTemplateIn) -> MailTemplateOut:
    with db() as conn:
        m = repo.create_mail_template(conn, repo.MailTemplate(
            id=None, name=body.name, mailjet_template_id=body.mailjet_template_id,
            is_default=body.is_default))
        return MailTemplateOut(id=m.id, name=m.name,
                               mailjet_template_id=m.mailjet_template_id,
                               is_default=m.is_default)


@app.put("/api/mail-templates/{tid}", response_model=MailTemplateOut, tags=["mailTemplates"])
def mail_templates_update(tid: int, body: MailTemplateIn) -> MailTemplateOut:
    with db() as conn:
        repo.update_mail_template(conn, repo.MailTemplate(
            id=tid, name=body.name, mailjet_template_id=body.mailjet_template_id,
            is_default=body.is_default))
        for m in repo.list_mail_templates(conn):
            if m.id == tid:
                return MailTemplateOut(id=m.id, name=m.name,
                                       mailjet_template_id=m.mailjet_template_id,
                                       is_default=m.is_default)
    raise ApiError(ERR_NOT_FOUND, f"Modèle d'email introuvable : {tid}", status=404)


@app.delete("/api/mail-templates/{tid}", response_model=OkOut, tags=["mailTemplates"])
def mail_templates_delete(tid: int) -> OkOut:
    with db() as conn:
        repo.delete_mail_template(conn, tid)
    return OkOut()


@app.post("/api/mail-templates/{tid}/default", response_model=OkOut, tags=["mailTemplates"])
def mail_templates_set_default(tid: int) -> OkOut:
    with db() as conn:
        repo.set_default_mail_template(conn, tid)
    return OkOut()


# --- printers.* + settings.* (imprimante) -------------------------------------

@app.get("/api/printers", response_model=PrintersOut, tags=["printers"])
def printers_list() -> PrintersOut:
    with db() as conn:
        selected = repo.get_setting(conn, PRINTER_KEY)
    return PrintersOut(
        printers=printing.list_printers(),
        default=printing.default_printer(),
        selected=selected,
    )


@app.post("/api/printers/test", response_model=JobAcceptedOut, status_code=202,
          tags=["printers"])
def printers_test(body: PrinterTestIn) -> JobAcceptedOut:
    """Lance un test d'impression (operation longue) : 202 + job_id, suivi en SSE."""
    name = (body.printer_name or "").strip()
    if not name:
        raise ApiError(ERR_VALIDATION, "Aucune imprimante sélectionnée.", status=400)
    if name not in printing.list_printers():
        raise ApiError(ERR_PRINTER_NOT_FOUND,
                       f"Imprimante introuvable : {name}", status=404)

    def task(report):
        report(0.1, f"Préparation du test sur {name}…")
        try:
            printing.print_test_page(name)
        except Exception as exc:  # noqa: BLE001
            raise ApiError(ERR_PRINT_FAILED, f"Échec de l'impression : {exc}")
        report(1.0, "Page de test envoyée.")
        return {"printer": name}

    return JobAcceptedOut(job_id=submit_job(task))


@app.put("/api/settings/printer", response_model=OkOut, tags=["settings"])
def settings_set_printer(body: PrinterSelectIn) -> OkOut:
    with db() as conn:
        repo.set_setting(conn, PRINTER_KEY, body.printer_name)
    return OkOut()


@app.get("/api/settings/print-types", response_model=PrintTypesOut, tags=["settings"])
def settings_print_types() -> PrintTypesOut:
    """Types reglables (noms de modeles + types de documents deja generes)."""
    names = {t.name for t in templates.list_templates()}
    with db() as conn:
        names |= set(repo.all_document_types(conn))
        cfg = print_settings.all_settings(conn)
    return PrintTypesOut(types=sorted(names), settings=cfg)


@app.get("/api/settings/print/{doc_type}", response_model=PrintConfigOut, tags=["settings"])
def settings_get_print(doc_type: str) -> PrintConfigOut:
    with db() as conn:
        cfg = print_settings.get_settings_for(conn, doc_type)
    return PrintConfigOut(paper=cfg.get("paper"), color=cfg.get("color"))


@app.put("/api/settings/print/{doc_type}", response_model=OkOut, tags=["settings"])
def settings_set_print(doc_type: str, body: PrintConfigIn) -> OkOut:
    with db() as conn:
        print_settings.set_settings_for(conn, doc_type, body.paper, body.color)
    return OkOut()


# --- actes.* ------------------------------------------------------------------

@app.get("/api/actes", response_model=ActeListOut, tags=["actes"])
def actes_list(search: str = "", include_inactive: bool = False,
               limit: Optional[int] = None, offset: int = 0) -> ActeListOut:
    with db() as conn:
        actes = repo.list_actes(conn, search=search,
                                actifs_seulement=not include_inactive,
                                limit=limit, offset=offset)
        total = repo.count_actes(conn, search=search,
                                 actifs_seulement=not include_inactive)
    return ActeListOut(
        items=[ActeOut(id=a.id, libelle=a.libelle, prix=a.prix, code=a.code,
                       actif=a.actif, sort_order=a.sort_order) for a in actes],
        total=total,
    )


@app.post("/api/actes", response_model=ActeOut, tags=["actes"])
def actes_create(body: ActeIn) -> ActeOut:
    try:
        with db() as conn:
            a = repo.create_acte(conn, repo.Acte(
                id=None, libelle=body.libelle, prix=body.prix, code=body.code,
                sort_order=body.sort_order))
        return ActeOut(id=a.id, libelle=a.libelle, prix=a.prix, code=a.code,
                       actif=a.actif, sort_order=a.sort_order)
    except Exception as exc:  # noqa: BLE001
        raise _err_from_engine(exc)


@app.put("/api/actes/{acte_id}", response_model=ActeOut, tags=["actes"])
def actes_update(acte_id: int, body: ActeIn) -> ActeOut:
    try:
        with db() as conn:
            existing = repo.get_acte(conn, acte_id)
            if existing is None:
                raise ApiError(ERR_NOT_FOUND, f"Acte introuvable : {acte_id}", status=404)
            repo.update_acte(conn, repo.Acte(
                id=acte_id, libelle=body.libelle, prix=body.prix, code=body.code,
                actif=existing.actif, sort_order=body.sort_order))
            a = repo.get_acte(conn, acte_id)
        return ActeOut(id=a.id, libelle=a.libelle, prix=a.prix, code=a.code,
                       actif=a.actif, sort_order=a.sort_order)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _err_from_engine(exc)


@app.post("/api/actes/{acte_id}/active", response_model=OkOut, tags=["actes"])
def actes_set_active(acte_id: int, body: ActeActiveIn) -> OkOut:
    with db() as conn:
        repo.set_acte_actif(conn, acte_id, body.actif)
    return OkOut()


# --- Operations longues : canal SSE -------------------------------------------

@app.get("/api/events/{job_id}", tags=["jobs"])
async def events(job_id: str):
    """Flux Server-Sent Events de progression/achevement d'une operation longue."""
    return StreamingResponse(
        STATE.jobs.stream(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# =============================================================================
# Demarrage du serveur (port ephemere loopback + jeton + handshake stdout)
# =============================================================================

def _init_db() -> None:
    """Backup pre-migration PUIS ouverture (migrations + anti-downgrade).

    Ordre impose par CLAUDE.md : `backup.backup_db()` doit s'executer AVANT
    `connect()` (qui migre la base en place). `connect()` ecrit en plus une copie
    etiquetee pre-migration et refuse une base plus recente (`SchemaTooNewError`).
    """
    backup.backup_db()
    conn = connect()
    # Un job 'en_cours' ne survit pas a un arret : marquer interrompu au demarrage
    # (coherent avec crm/app.py ; base partagee).
    try:
        repo.mark_stale_jobs_interrupted(conn)
    except Exception:  # noqa: BLE001
        pass
    STATE.conn = conn


def create_server(host: str, port: int, token: str) -> tuple[uvicorn.Server, socket.socket, int]:
    """Lie un socket loopback (port ephemere si port=0) et prepare le serveur."""
    STATE.token = token
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    actual_port = sock.getsockname()[1]
    config = uvicorn.Config(app, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    return server, sock, actual_port


def run(host: str = "127.0.0.1", port: int = 0, token: Optional[str] = None) -> None:
    """Demarre le backend : init base, handshake stdout, boucle ASGI (bloquant)."""
    token = token or os.environ.get("CRM_TOKEN") or secrets.token_urlsafe(32)
    _init_db()
    server, sock, actual_port = create_server(host, port, token)
    # Handshake : la coquille (Tauri) lit cette ligne sur stdout pour decouvrir le
    # port effectif et le jeton, puis ouvre la WebView pointant sur l'UI.
    handshake = {"host": host, "port": actual_port, "token": token,
                 "version": version.__version__}
    print(HANDSHAKE_PREFIX + json.dumps(handshake), flush=True)
    asyncio.run(server.serve(sockets=[sock]))


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Backend de services du Cabinet CRM.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Interface d'ecoute (loopback par defaut).")
    parser.add_argument("--port", type=int, default=0,
                        help="Port (0 = ephemere, choisi par l'OS).")
    parser.add_argument("--token", default=None,
                        help="Jeton de session (genere si absent).")
    args = parser.parse_args(argv)
    run(host=args.host, port=args.port, token=args.token)


if __name__ == "__main__":
    main()
