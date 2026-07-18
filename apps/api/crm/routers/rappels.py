"""Routeur Rappels : CRUD, transitions d'état, badge cloche, lien wa.me.

Suit le même patron que les autres routeurs (patients, documents, …) :
- APIRouter prefix="/api"
- Connexion SQLite via `core.db()` (context manager à verrou)
- Erreurs via `core.ApiError`
- Modèles Pydantic In/Out

Routes exposées (cf. design D8) :
  POST   /api/rappels                       Créer
  GET    /api/rappels                       Lister (filtres : etat, patient_id)
  GET    /api/rappels/count-actifs          Badge cloche
  GET    /api/rappels/{id}                  Détail
  PUT    /api/rappels/{id}                  Modifier (si état le permet)
  PATCH  /api/rappels/{id}/ignorer          Marquer lu/traité (cloche)
  PATCH  /api/rappels/{id}/envoye           Marquer envoyé (après wa.me)
  PATCH  /api/rappels/{id}/traite           Marquer traité manuellement
  PATCH  /api/rappels/{id}/annuler          Annuler
  GET    /api/rappels/{id}/whatsapp-link    Construire le lien wa.me
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from crm import repo, server as core
from crm import rappels as rappels_logic

router = APIRouter(prefix="/api", tags=["rappels"])


# =============================================================================
# Modèles Pydantic (contrat OpenAPI)
# =============================================================================


class RappelIn(BaseModel):
    type: str  # alerte_interne | message_patient
    titre: str
    echeance: str  # ISO datetime ou date
    patient_id: Optional[int] = None
    document_id: Optional[int] = None
    message: Optional[str] = None


class RappelOut(BaseModel):
    id: int
    type: str
    titre: str
    echeance: str
    etat: str
    lu: bool
    patient_id: Optional[int] = None
    document_id: Optional[int] = None
    message: Optional[str] = None
    created_at: Optional[str] = None
    notified_at: Optional[str] = None
    sent_at: Optional[str] = None
    patient_display: Optional[str] = None  # "NOM Prénom" si rattaché à un patient


class RappelListOut(BaseModel):
    items: list[RappelOut]
    total: int


class CountActifsOut(BaseModel):
    count: int


class ProcessDusOut(BaseModel):
    """Résultat du traitement des rappels dus (filet de sécurité au démarrage)."""

    processed: int


class WhatsAppLinkOut(BaseModel):
    url: str
    phone_id: Optional[int] = None


# =============================================================================
# Sérialisation
# =============================================================================


def _rappel_out(r: repo.Rappel, patient_display: Optional[str] = None) -> RappelOut:
    return RappelOut(
        id=r.id,
        type=r.type,
        titre=r.titre,
        echeance=r.echeance,
        etat=r.etat,
        lu=r.lu,
        patient_id=r.patient_id,
        document_id=r.document_id,
        message=r.message,
        created_at=r.created_at,
        notified_at=r.notified_at,
        sent_at=r.sent_at,
        patient_display=patient_display,
    )


def _get_or_404(conn, rappel_id: int) -> repo.Rappel:
    r = repo.get_rappel(conn, rappel_id)
    if r is None:
        raise core.ApiError(
            core.ERR_NOT_FOUND, f"Rappel introuvable : {rappel_id}", status=404
        )
    return r


# =============================================================================
# Routes
# =============================================================================


@router.post("/rappels", response_model=RappelOut, status_code=201)
def rappels_create(body: RappelIn) -> RappelOut:
    """Crée un nouveau rappel (avec validation métier)."""
    try:
        with core.db() as conn:
            rappels_logic.validate_rappel(
                conn,
                type_rappel=body.type,
                patient_id=body.patient_id,
                message=body.message,
                titre=body.titre,
                echeance=body.echeance,
            )
            r = repo.create_rappel(
                conn,
                repo.Rappel(
                    id=None,
                    type=body.type,
                    titre=body.titre,
                    echeance=body.echeance,
                    patient_id=body.patient_id,
                    document_id=body.document_id,
                    message=body.message,
                ),
            )
        return _rappel_out(r)
    except rappels_logic.RappelValidationError as exc:
        raise core.ApiError(core.ERR_VALIDATION, str(exc), status=400)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.get("/rappels", response_model=RappelListOut)
def rappels_list(
    etat: Optional[str] = None,
    patient_id: Optional[int] = None,
    limit: Optional[int] = 100,
    offset: int = 0,
) -> RappelListOut:
    """Liste les rappels, filtrables par état (virgule-séparés) et/ou patient."""
    etats: Optional[list[str]] = None
    if etat:
        etats = [e.strip() for e in etat.split(",") if e.strip()]

    with core.db() as conn:
        items = repo.list_rappels(
            conn, etats=etats, patient_id=patient_id, limit=limit, offset=offset
        )
        total = repo.count_rappels(conn, etats=etats, patient_id=patient_id)
    return RappelListOut(items=[_rappel_out(r, display) for r, display in items], total=total)


@router.get("/rappels/count-actifs", response_model=CountActifsOut)
def rappels_count_actifs() -> CountActifsOut:
    """Nombre de rappels actifs non lus pour le badge cloche.

    Actifs = etat IN ('du', 'a_envoyer') AND lu = 0.
    """
    with core.db() as conn:
        count = repo.count_rappels_actifs(conn)
    return CountActifsOut(count=count)


@router.post("/rappels/process-dus", response_model=ProcessDusOut)
def rappels_process_dus() -> ProcessDusOut:
    """Traite les rappels échus (filet de sécurité au démarrage du frontend).

    Effectue la transition atomique planifie → du/a_envoyer pour tous les
    rappels dont l'échéance est dépassée. Idempotent : seuls les rappels à
    l'état `planifie` sont touchés (cf. `rappels.traiter_rappels_dus`).

    Appelé par le frontend au montage pour garantir que le badge et la liste
    reflètent les rappels dus, même si la tâche planifiée Windows n'a pas tourné
    depuis l'ouverture précédente.
    """
    try:
        with core.db() as conn:
            traites = rappels_logic.traiter_rappels_dus(conn)
        return ProcessDusOut(processed=len(traites))
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.get("/rappels/{rappel_id}", response_model=RappelOut)
def rappels_get(rappel_id: int) -> RappelOut:
    with core.db() as conn:
        r = _get_or_404(conn, rappel_id)
    return _rappel_out(r)


@router.put("/rappels/{rappel_id}", response_model=RappelOut)
def rappels_update(rappel_id: int, body: RappelIn) -> RappelOut:
    """Modifie un rappel. Refusé si l'état ne le permet plus (envoyé/traité/annulé)."""
    try:
        with core.db() as conn:
            r = _get_or_404(conn, rappel_id)
            if r.etat in repo.RAPPEL_ETATS_TERMINAUX:
                raise core.ApiError(
                    core.ERR_VALIDATION,
                    f"Ce rappel est à l'état « {r.etat} » et ne peut plus être modifié.",
                    status=409,
                )
            rappels_logic.validate_rappel(
                conn,
                type_rappel=body.type,
                patient_id=body.patient_id,
                message=body.message,
                titre=body.titre,
                echeance=body.echeance,
            )
            r.titre = body.titre
            r.echeance = body.echeance
            r.patient_id = body.patient_id
            r.document_id = body.document_id
            r.message = body.message
            updated = repo.update_rappel(conn, r)
        return _rappel_out(updated)
    except rappels_logic.RappelValidationError as exc:
        raise core.ApiError(core.ERR_VALIDATION, str(exc), status=400)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.patch("/rappels/{rappel_id}/ignorer", response_model=RappelOut)
def rappels_ignorer(rappel_id: int) -> RappelOut:
    """Ignore un rappel depuis la cloche.

    - alerte_interne (état 'du')    → passe à 'traite'
    - message_patient (état 'a_envoyer') → reste 'a_envoyer', lu=1 (sort du badge)
    """
    with core.db() as conn:
        _get_or_404(conn, rappel_id)
        updated = repo.marquer_rappel_lu(conn, rappel_id)
        if updated is None:
            raise core.ApiError(
                core.ERR_NOT_FOUND, f"Rappel introuvable : {rappel_id}", status=404
            )
    return _rappel_out(updated)


@router.patch("/rappels/{rappel_id}/envoye", response_model=RappelOut)
def rappels_marquer_envoye(rappel_id: int) -> RappelOut:
    """Marque un rappel comme envoyé après confirmation de l'envoi WhatsApp."""
    with core.db() as conn:
        r = _get_or_404(conn, rappel_id)
        if r.type != "message_patient":
            raise core.ApiError(
                core.ERR_VALIDATION,
                "Seuls les rappels de type « message_patient » peuvent être marqués envoyés.",
                status=400,
            )
        updated = repo.marquer_rappel_envoye(conn, rappel_id)
        if updated is None:
            raise core.ApiError(
                core.ERR_NOT_FOUND, f"Rappel introuvable : {rappel_id}", status=404
            )
    return _rappel_out(updated)


@router.patch("/rappels/{rappel_id}/traite", response_model=RappelOut)
def rappels_marquer_traite(rappel_id: int) -> RappelOut:
    """Marque un rappel comme traité manuellement."""
    with core.db() as conn:
        _get_or_404(conn, rappel_id)
        updated = repo.marquer_rappel_traite(conn, rappel_id)
        if updated is None:
            raise core.ApiError(
                core.ERR_NOT_FOUND, f"Rappel introuvable : {rappel_id}", status=404
            )
    return _rappel_out(updated)


@router.patch("/rappels/{rappel_id}/annuler", response_model=RappelOut)
def rappels_annuler(rappel_id: int) -> RappelOut:
    """Annule un rappel. Empêche toute mise en file ou notification future."""
    with core.db() as conn:
        r = _get_or_404(conn, rappel_id)
        if r.etat in {"envoye", "traite"}:
            raise core.ApiError(
                core.ERR_VALIDATION,
                f"Ce rappel est à l'état « {r.etat} » et ne peut pas être annulé.",
                status=409,
            )
        updated = repo.annuler_rappel(conn, rappel_id)
        if updated is None:
            raise core.ApiError(
                core.ERR_NOT_FOUND, f"Rappel introuvable : {rappel_id}", status=404
            )
    return _rappel_out(updated)


@router.get("/rappels/{rappel_id}/whatsapp-link", response_model=WhatsAppLinkOut)
def rappels_whatsapp_link(
    rappel_id: int,
    phone_id: Optional[int] = None,
) -> WhatsAppLinkOut:
    """Construit le lien wa.me pour un rappel de type message_patient.

    Si `phone_id` est fourni, utilise ce numéro spécifique (sélecteur multi-numéros).
    Sinon utilise le premier numéro is_whatsapp=1 du patient.
    """
    try:
        with core.db() as conn:
            r = _get_or_404(conn, rappel_id)
            url = rappels_logic.get_whatsapp_link_for_rappel(conn, r, phone_id=phone_id)
        return WhatsAppLinkOut(url=url, phone_id=phone_id)
    except rappels_logic.RappelValidationError as exc:
        raise core.ApiError(core.ERR_VALIDATION, str(exc), status=400)
    except ValueError as exc:
        raise core.ApiError(core.ERR_VALIDATION, str(exc), status=400)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)
