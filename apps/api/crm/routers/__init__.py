"""Routeurs de la facade de services (un module par domaine UI).

Chaque module definit un `router` (FastAPI `APIRouter`) qui reutilise le moteur
existant (`crm/repo.py`, `crm/generator.py`, ...) **sans le modifier**, et l'infra
partagee de `crm/server.py` (connexion verrouillee `db()`, operations longues
`submit_job()`, erreurs structurees `ApiError`). L'enregistrement se fait par
`register_all(app)`, appele en bas de `crm/server.py` (apres que l'infra et `app`
sont definis) : aucun cycle d'import.
"""

from __future__ import annotations

from fastapi import FastAPI


def register_all(app: FastAPI) -> None:
    """Inclut tous les routeurs de domaine dans l'application FastAPI.

    Idempotent : garde-fou contre une double inclusion (ex. ré-import accidentel).
    Note : lancer le backend via `crm_server.py` (point d'entrée réel), PAS via
    `python -m crm.server` (ce dernier crée deux instances du module — `__main__`
    et `crm.server` — et casse l'import des routeurs).
    """
    if getattr(app.state, "_routers_registered", False):
        return
    app.state._routers_registered = True
    from . import (
        clinical,
        dashboard,
        documents,
        finances,
        jobs,
        patients,
        prestataires,
    )

    for module in (
        patients,
        clinical,
        documents,
        finances,
        prestataires,
        jobs,
        dashboard,
    ):
        app.include_router(module.router)
