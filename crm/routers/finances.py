"""Routeur finances : encaissements/creances (onglet Paiements) et dependes
(onglet Depenses), filtres + totaux. Calque `show_paiements` / `show_depenses`.

Les mutations de depenses (creation, reglement, suppression) vivent dans le
routeur `prestataires` (elles sont rattachees a un prestataire) et sont
reutilisees par l'ecran Finances.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from crm import repo, server as core
from crm.routers.prestataires import depense_out, DepenseOut

router = APIRouter(prefix="/api", tags=["finances"])


# --- Modeles ------------------------------------------------------------------

class FinanceRow(BaseModel):
    kind: str           # 'creance' | 'paiement'
    nature: str = ""    # 'note' | 'acte' (creances)
    source_id: int
    patient_id: int
    patient_display: str
    libelle: str
    montant: float
    reste: float = 0.0
    date: Optional[str] = None
    statut: str
    mode: Optional[str] = None


class FinanceSummary(BaseModel):
    label: str
    total: float


class PaiementsOut(BaseModel):
    items: list[FinanceRow]
    total: int
    summary: FinanceSummary


class DepenseRow(BaseModel):
    depense: DepenseOut
    prestataire_id: int
    prestataire_display: str


class DepensesSummary(BaseModel):
    du: float
    regle: float
    reste: float


class DepensesOut(BaseModel):
    items: list[DepenseRow]
    total: int
    summary: DepensesSummary


# --- Paiements / creances -----------------------------------------------------

@router.get("/finances/paiements", response_model=PaiementsOut)
def finances_paiements(statut: str = "en_attente", search: str = "",
                       date_from: str = "", date_to: str = "",
                       limit: Optional[int] = 20, offset: int = 0) -> PaiementsOut:
    with core.db() as conn:
        if statut == "en_attente":
            # Vue unifiee des creances (notes non encaissees + actes non soldes).
            total = repo.count_creances(conn, search=search, date_from=date_from,
                                        date_to=date_to)
            cr = repo.list_creances(conn, search=search, date_from=date_from,
                                    date_to=date_to, limit=limit, offset=offset)
            items = [FinanceRow(
                kind="creance", nature=c.nature, source_id=c.source_id,
                patient_id=c.patient.id, patient_display=c.patient.display,
                libelle=c.libelle, montant=c.montant, reste=c.reste, date=c.date,
                statut=c.statut) for c in cr]
            summary = FinanceSummary(
                label="Total à recouvrer",
                total=repo.total_creances(conn, search=search, date_from=date_from,
                                          date_to=date_to))
        else:
            total = repo.count_paiements(conn, search=search, statut=statut,
                                         date_from=date_from, date_to=date_to)
            rows = repo.list_paiements_filtered(conn, search=search, statut=statut,
                                                limit=limit, offset=offset,
                                                date_from=date_from, date_to=date_to)
            items = [FinanceRow(
                kind="paiement", nature="note", source_id=pa.id,
                patient_id=pt.id, patient_display=pt.display,
                libelle=pa.notes or "Paiement", montant=pa.montant, reste=0.0,
                date=pa.date_encaissement or pa.date_echeance, statut=pa.statut,
                mode=pa.mode) for pa, pt in rows]
            if statut == "encaisse":
                summary = FinanceSummary(
                    label="Total encaissé",
                    total=repo.total_encaisse(conn, date_from=date_from,
                                              date_to=date_to))
            else:
                summary = FinanceSummary(
                    label="Total (tous statuts)",
                    total=repo.total_paiements(conn, search=search, statut="tous",
                                               date_from=date_from, date_to=date_to))
    return PaiementsOut(items=items, total=total, summary=summary)


# --- Depenses -----------------------------------------------------------------

@router.get("/finances/depenses", response_model=DepensesOut)
def finances_depenses(statut: str = "en_attente", search: str = "",
                      date_from: str = "", date_to: str = "",
                      limit: Optional[int] = 20, offset: int = 0) -> DepensesOut:
    with core.db() as conn:
        total = repo.count_depenses(conn, search=search, statut=statut,
                                    date_from=date_from, date_to=date_to)
        rows = repo.list_depenses_filtered(conn, search=search, statut=statut,
                                           limit=limit, offset=offset,
                                           date_from=date_from, date_to=date_to)
        du, regle, reste = repo.total_depenses(conn, search=search, statut=statut,
                                               date_from=date_from, date_to=date_to)
    items = [DepenseRow(depense=depense_out(dep),
                        prestataire_id=pr.id if pr else 0,
                        prestataire_display=pr.display if pr else (dep.libelle or "—"))
             for dep, pr in rows]
    return DepensesOut(items=items, total=total,
                       summary=DepensesSummary(du=du, regle=regle, reste=reste))
