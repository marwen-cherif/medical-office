"""Routeur clinique : plans de traitement, actes realises (prestations),
reglements (par acte + cascade), notes/paiements, encaissements, historique.

Reutilise `crm/repo.py` sans le modifier. Source unique du du = les actes
(`plans-de-traitement`) : generer une note ne cree aucun paiement.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from crm import repo, server as core
from crm.routers.patients import patient_out, PatientOut

router = APIRouter(prefix="/api", tags=["clinical"])


# --- Modeles ------------------------------------------------------------------

class PrestationOut(BaseModel):
    id: int
    patient_id: int
    plan_id: Optional[int] = None
    acte_id: Optional[int] = None
    libelle: str
    montant: float
    montant_regle: float
    reste: float
    statut: str
    facturable: bool
    date_acte: Optional[str] = None
    dents: Optional[str] = None
    note: Optional[str] = None


class TotauxOut(BaseModel):
    du: float
    encaisse: float
    reste: float


class PlanOut(BaseModel):
    id: int
    patient_id: int
    titre: str
    notes: Optional[str] = None
    created_at: Optional[str] = None


class PlanGroupOut(BaseModel):
    plan: PlanOut
    totaux: TotauxOut
    prestations: list[PrestationOut]


class PaiementOut(BaseModel):
    id: int
    patient_id: int
    montant: float
    montant_regle: float
    reste: float
    statut: str
    mode: Optional[str] = None
    date_echeance: Optional[str] = None
    date_encaissement: Optional[str] = None
    notes: Optional[str] = None


class ClinicalOut(BaseModel):
    notes_en_attente: list[PaiementOut]
    isoles: list[PrestationOut]
    plans: list[PlanGroupOut]
    total_a_regler: float


class EncaissementOut(BaseModel):
    nature: str
    source_id: int
    libelle: str
    montant: float
    mode: Optional[str] = None
    date: Optional[str] = None


class EncaissementsOut(BaseModel):
    items: list[EncaissementOut]
    total: int
    solde: TotauxOut


class CreanceOut(BaseModel):
    nature: str
    source_id: int
    libelle: str
    montant: float
    reste: float
    date: Optional[str] = None
    statut: str


class AuditOut(BaseModel):
    ts: str
    action: str
    detail: Any = None


class PlanIn(BaseModel):
    titre: str
    notes: Optional[str] = None


class PrestationIn(BaseModel):
    libelle: str
    montant: float = 0.0
    plan_id: Optional[int] = None
    acte_id: Optional[int] = None
    date_acte: Optional[str] = None
    dents: Optional[str] = None
    note: Optional[str] = None


class ReglementIn(BaseModel):
    montant: float
    mode: Optional[str] = None
    date_reglement: Optional[str] = None


class CascadeIn(BaseModel):
    montant: float
    mode: Optional[str] = None
    date_reglement: Optional[str] = None
    include_notes: bool = False


class CascadeOut(BaseModel):
    alloue: float
    reste: float
    lignes: list[dict]


class PaiementIn(BaseModel):
    montant: float
    mode: Optional[str] = None
    date_echeance: Optional[str] = None
    date_encaissement: Optional[str] = None
    statut: str = "en_attente"
    notes: Optional[str] = None


class EncaisserIn(BaseModel):
    mode: Optional[str] = None
    date_encaissement: Optional[str] = None


# --- Serialisation ------------------------------------------------------------

def prestation_out(p: repo.Prestation) -> PrestationOut:
    return PrestationOut(
        id=p.id, patient_id=p.patient_id, plan_id=p.plan_id, acte_id=p.acte_id,
        libelle=p.libelle, montant=p.montant, montant_regle=p.montant_regle,
        reste=p.reste, statut=p.statut, facturable=p.facturable,
        date_acte=p.date_acte, dents=p.dents, note=p.note,
    )


def plan_out(pl: repo.PlanTraitement) -> PlanOut:
    return PlanOut(id=pl.id, patient_id=pl.patient_id, titre=pl.titre,
                   notes=pl.notes, created_at=pl.created_at)


def paiement_out(pa: repo.Paiement) -> PaiementOut:
    return PaiementOut(
        id=pa.id, patient_id=pa.patient_id, montant=pa.montant,
        montant_regle=pa.montant_regle, reste=pa.reste, statut=pa.statut,
        mode=pa.mode, date_echeance=pa.date_echeance,
        date_encaissement=pa.date_encaissement, notes=pa.notes,
    )


# --- Lecture (onglets de la fiche) --------------------------------------------

@router.get("/patients/{patient_id}/clinical", response_model=ClinicalOut)
def patient_clinical(patient_id: int) -> ClinicalOut:
    with core.db() as conn:
        notes = [pa for pa in repo.list_paiements(conn, patient_id)
                 if pa.statut in ("en_attente", "regle_partiellement")]
        isoles = repo.list_prestations(conn, patient_id, plan_id=None)
        plans = repo.list_plans(conn, patient_id)
        groups: list[PlanGroupOut] = []
        for pl in plans:
            pres = repo.list_prestations(conn, patient_id, plan_id=pl.id)
            du, enc, reste = repo.plan_totaux(conn, pl.id)
            groups.append(PlanGroupOut(
                plan=plan_out(pl), totaux=TotauxOut(du=du, encaisse=enc, reste=reste),
                prestations=[prestation_out(x) for x in pres],
            ))
        a_regler = repo.list_prestations_a_regler(conn, patient_id)
    return ClinicalOut(
        notes_en_attente=[paiement_out(pa) for pa in notes],
        isoles=[prestation_out(x) for x in isoles],
        plans=groups,
        total_a_regler=sum(pr.reste for pr in a_regler),
    )


@router.get("/patients/{patient_id}/encaissements", response_model=EncaissementsOut)
def patient_encaissements(patient_id: int, limit: Optional[int] = 20,
                          offset: int = 0) -> EncaissementsOut:
    with core.db() as conn:
        items = repo.list_encaissements_patient(conn, patient_id, limit=limit,
                                                offset=offset)
        total = repo.count_encaissements_patient(conn, patient_id)
        du, enc, reste = repo.solde_patient(conn, patient_id)
    return EncaissementsOut(
        items=[EncaissementOut(nature=e.nature, source_id=e.source_id,
                               libelle=e.libelle, montant=e.montant, mode=e.mode,
                               date=e.date) for e in items],
        total=total, solde=TotauxOut(du=du, encaisse=enc, reste=reste),
    )


@router.get("/patients/{patient_id}/creances", response_model=list[CreanceOut])
def patient_creances(patient_id: int, include_notes: bool = False) -> list[CreanceOut]:
    with core.db() as conn:
        cr = repo.creances_patient(conn, patient_id, include_notes=include_notes)
    return [CreanceOut(nature=c.nature, source_id=c.source_id, libelle=c.libelle,
                       montant=c.montant, reste=c.reste, date=c.date,
                       statut=c.statut) for c in cr]


@router.get("/patients/{patient_id}/audit", response_model=list[AuditOut])
def patient_audit(patient_id: int, limit: int = 200) -> list[AuditOut]:
    with core.db() as conn:
        rows = repo.list_audit_patient(conn, patient_id, limit=limit)
    return [AuditOut(ts=ts, action=action, detail=repo.parse_audit_detail(detail))
            for ts, action, detail in rows]


# --- Plans --------------------------------------------------------------------

@router.post("/patients/{patient_id}/plans", response_model=PlanOut)
def plan_create(patient_id: int, body: PlanIn) -> PlanOut:
    try:
        with core.db() as conn:
            pl = repo.create_plan(conn, patient_id, body.titre.strip(),
                                  body.notes or None)
            repo.log_audit(conn, "plan_cree", {"plan_id": pl.id, "titre": pl.titre},
                           patient_id=patient_id)
        return plan_out(pl)
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.put("/plans/{plan_id}", response_model=PlanOut)
def plan_update(plan_id: int, body: PlanIn) -> PlanOut:
    try:
        with core.db() as conn:
            existing = repo.get_plan(conn, plan_id)
            if existing is None:
                raise core.ApiError(core.ERR_NOT_FOUND,
                                    f"Plan introuvable : {plan_id}", status=404)
            repo.update_plan(conn, plan_id, body.titre.strip(), body.notes or None)
            repo.log_audit(conn, "plan_modifie", {"plan_id": plan_id},
                           patient_id=existing.patient_id)
            pl = repo.get_plan(conn, plan_id)
        return plan_out(pl)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.delete("/plans/{plan_id}", response_model=core.OkOut)
def plan_delete(plan_id: int) -> core.OkOut:
    with core.db() as conn:
        existing = repo.get_plan(conn, plan_id)
        if existing is None:
            raise core.ApiError(core.ERR_NOT_FOUND,
                                f"Plan introuvable : {plan_id}", status=404)
        repo.delete_plan(conn, plan_id)
        repo.log_audit(conn, "plan_supprime", {"plan_id": plan_id},
                       patient_id=existing.patient_id)
    return core.OkOut()


# --- Prestations (actes realises) ---------------------------------------------

@router.post("/patients/{patient_id}/prestations", response_model=PrestationOut)
def prestation_create(patient_id: int, body: PrestationIn) -> PrestationOut:
    try:
        with core.db() as conn:
            pres = repo.create_prestation(
                conn, patient_id, body.libelle.strip(), body.montant,
                plan_id=body.plan_id, acte_id=body.acte_id,
                date_acte=body.date_acte, dents=body.dents, note=body.note)
            repo.log_audit(conn, "acte_cree",
                           {"prestation_id": pres.id, "libelle": pres.libelle},
                           patient_id=patient_id)
        return prestation_out(pres)
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.put("/prestations/{prestation_id}", response_model=PrestationOut)
def prestation_update(prestation_id: int, body: PrestationIn) -> PrestationOut:
    try:
        with core.db() as conn:
            existing = repo.get_prestation(conn, prestation_id)
            if existing is None:
                raise core.ApiError(core.ERR_NOT_FOUND,
                                    f"Acte introuvable : {prestation_id}", status=404)
            repo.update_prestation(
                conn, prestation_id, libelle=body.libelle.strip(),
                montant=body.montant, plan_id=body.plan_id, acte_id=body.acte_id,
                date_acte=body.date_acte, dents=body.dents, note=body.note)
            repo.log_audit(conn, "acte_modifie", {"prestation_id": prestation_id},
                           patient_id=existing.patient_id)
            pres = repo.get_prestation(conn, prestation_id)
        return prestation_out(pres)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.delete("/prestations/{prestation_id}", response_model=core.OkOut)
def prestation_delete(prestation_id: int) -> core.OkOut:
    try:
        with core.db() as conn:
            existing = repo.get_prestation(conn, prestation_id)
            if existing is None:
                raise core.ApiError(core.ERR_NOT_FOUND,
                                    f"Acte introuvable : {prestation_id}", status=404)
            repo.delete_prestation(conn, prestation_id)
            repo.log_audit(conn, "acte_supprime", {"prestation_id": prestation_id},
                           patient_id=existing.patient_id)
        return core.OkOut()
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.post("/prestations/{prestation_id}/reglement", response_model=PrestationOut)
def prestation_reglement(prestation_id: int, body: ReglementIn) -> PrestationOut:
    try:
        with core.db() as conn:
            existing = repo.get_prestation(conn, prestation_id)
            if existing is None:
                raise core.ApiError(core.ERR_NOT_FOUND,
                                    f"Acte introuvable : {prestation_id}", status=404)
            pres = repo.add_prestation_reglement(
                conn, prestation_id, body.montant, mode=body.mode,
                date_reglement=body.date_reglement)
            repo.log_audit(conn, "acte_regle",
                           {"prestation_id": prestation_id, "montant": body.montant,
                            "mode": body.mode}, patient_id=existing.patient_id)
        return prestation_out(pres)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.post("/patients/{patient_id}/regler", response_model=CascadeOut)
def patient_regler(patient_id: int, body: CascadeIn) -> CascadeOut:
    try:
        with core.db() as conn:
            res = repo.regler_creances(
                conn, patient_id, body.montant, mode=body.mode,
                date_reglement=body.date_reglement, include_notes=body.include_notes)
            repo.log_audit(conn, "reglement_cascade",
                           {"montant": body.montant, "alloue": res.get("alloue"),
                            "mode": body.mode}, patient_id=patient_id)
        return CascadeOut(alloue=res.get("alloue", 0.0), reste=res.get("reste", 0.0),
                          lignes=res.get("lignes", []))
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


# --- Paiements / notes --------------------------------------------------------

@router.post("/patients/{patient_id}/paiements", response_model=PaiementOut)
def paiement_create(patient_id: int, body: PaiementIn) -> PaiementOut:
    try:
        with core.db() as conn:
            pa = repo.create_paiement(conn, repo.Paiement(
                id=None, patient_id=patient_id, montant=body.montant,
                statut=body.statut, mode=body.mode,
                date_echeance=body.date_echeance,
                date_encaissement=body.date_encaissement, notes=body.notes))
            repo.log_audit(conn, "paiement_cree",
                           {"paiement_id": pa.id, "montant": pa.montant},
                           patient_id=patient_id)
        return paiement_out(pa)
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.post("/paiements/{paiement_id}/reglement", response_model=PaiementOut)
def paiement_reglement(paiement_id: int, body: ReglementIn) -> PaiementOut:
    """Enregistre un versement (partiel ou solde) sur une note, comme pour un acte."""
    try:
        with core.db() as conn:
            existing = repo.get_paiement(conn, paiement_id)
            if existing is None:
                raise core.ApiError(core.ERR_NOT_FOUND,
                                    f"Note introuvable : {paiement_id}", status=404)
            pa = repo.add_paiement_reglement(
                conn, paiement_id, body.montant, mode=body.mode,
                date_reglement=body.date_reglement)
            repo.log_audit(conn, "paiement_regle",
                           {"paiement_id": paiement_id, "montant": body.montant,
                            "mode": body.mode}, patient_id=existing.patient_id)
        return paiement_out(pa)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.post("/paiements/{paiement_id}/encaisser", response_model=core.OkOut)
def paiement_encaisser(paiement_id: int, body: EncaisserIn) -> core.OkOut:
    """Solde ENTIEREMENT une note (raccourci « encaisser » en un clic)."""
    with core.db() as conn:
        repo.mark_paiement_encaisse(conn, paiement_id, when=body.date_encaissement,
                                    mode=body.mode)
        repo.log_audit(conn, "paiement_encaisse", {"paiement_id": paiement_id})
    return core.OkOut()


@router.delete("/paiements/{paiement_id}", response_model=core.OkOut)
def paiement_delete(paiement_id: int) -> core.OkOut:
    try:
        with core.db() as conn:
            repo.delete_paiement(conn, paiement_id)
            repo.log_audit(conn, "paiement_supprime", {"paiement_id": paiement_id})
        return core.OkOut()
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)
