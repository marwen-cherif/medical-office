"""Routeur tableau de bord : agregats (KPI), donnees des graphiques, repartition
des documents et activite recente, sur une periode. Calque `_refresh_dashboard`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from crm import repo, server as core

router = APIRouter(prefix="/api", tags=["dashboard"])


class KpisOut(BaseModel):
    ca_encaisse: float
    encours: float
    nb_paiements_encaisses: int
    nb_documents: int
    nb_brouillons: int
    nb_envoyes: int
    nb_nouveaux_patients: int
    nb_patients: int
    nb_patients_impayes: int
    depenses_reglees: float
    dette_fournisseurs: float
    solde_net: float


class DocTypeCount(BaseModel):
    type: str
    count: int


class AuditLine(BaseModel):
    ts: str
    action: str
    detail: Any = None


class DashboardOut(BaseModel):
    kpis: KpisOut
    documents_by_type: list[DocTypeCount]
    recent_activity: list[AuditLine]


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(date_from: str = "", date_to: str = "") -> DashboardOut:
    with core.db() as conn:
        ca = repo.total_encaisse(conn, date_from=date_from, date_to=date_to)
        encours = repo.total_creances(conn, date_from=date_from, date_to=date_to)
        depenses = repo.total_regle_periode(conn, date_from=date_from, date_to=date_to)
        _, _, dette = repo.total_depenses(conn, statut="tous")
        kpis = KpisOut(
            ca_encaisse=ca,
            encours=encours,
            nb_paiements_encaisses=repo.count_paiements(
                conn, statut="encaisse", date_from=date_from, date_to=date_to),
            nb_documents=repo.count_documents(conn, None, date_from, date_to),
            nb_brouillons=repo.count_documents(conn, "brouillon", date_from, date_to),
            nb_envoyes=repo.count_documents(conn, "envoye", date_from, date_to),
            nb_nouveaux_patients=repo.count_patients_new(conn, date_from, date_to),
            nb_patients=repo.count_patients(conn),
            nb_patients_impayes=repo.count_patients(conn, filtre="impayes"),
            depenses_reglees=depenses,
            dette_fournisseurs=dette,
            solde_net=ca - depenses,
        )
        by_type = [DocTypeCount(type=t, count=n)
                   for t, n in repo.documents_by_type(conn, date_from, date_to)]
        audit = [AuditLine(ts=ts, action=action,
                           detail=repo.parse_audit_detail(detail))
                 for ts, action, detail in repo.list_audit(
                     conn, limit=12, date_from=date_from, date_to=date_to)]
    return DashboardOut(kpis=kpis, documents_by_type=by_type, recent_activity=audit)
