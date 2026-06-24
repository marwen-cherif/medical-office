"""Routeur Patients : liste/recherche/pagination, fiche, CRUD, anti-doublon.

Reutilise `crm/repo.py` sans le modifier. Les dates transitent en **ISO**
(`YYYY-MM-DD`) cote contrat (le frontend gere l'affichage FR).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from crm import repo, server as core

router = APIRouter(prefix="/api", tags=["patients"])


# --- Modeles (contrat OpenAPI) ------------------------------------------------

class PatientOut(BaseModel):
    id: int
    nom: str
    prenom: str
    display: str
    date_naissance: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None


class PatientIn(BaseModel):
    nom: str
    prenom: str
    date_naissance: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None
    force: bool = False  # cree malgre un doublon detecte (confirmation utilisateur)


class PatientListOut(BaseModel):
    items: list[PatientOut]
    total: int


class SoldeOut(BaseModel):
    du: float
    encaisse: float
    reste: float


class PatientDetailOut(BaseModel):
    patient: PatientOut
    solde: SoldeOut
    nb_documents: int
    nb_encaissements: int
    has_sent: bool
    nb_actes_a_regler: int
    total_a_regler: float


class MatchOut(BaseModel):
    matches: list[PatientOut]


class DuplicateWarning(BaseModel):
    duplicate: bool
    match: Optional[PatientOut] = None


# --- Serialisation ------------------------------------------------------------

def patient_out(p: repo.Patient) -> PatientOut:
    return PatientOut(
        id=p.id, nom=p.nom, prenom=p.prenom, display=p.display,
        date_naissance=p.date_naissance, email=p.email, telephone=p.telephone,
        adresse=p.adresse, notes=p.notes,
    )


def _to_patient(body: PatientIn, patient_id: Optional[int] = None) -> repo.Patient:
    return repo.Patient(
        id=patient_id, nom=body.nom.strip(), prenom=(body.prenom or "").strip(),
        date_naissance=body.date_naissance or None, email=body.email or None,
        telephone=body.telephone or None, adresse=body.adresse or None,
        notes=body.notes or None,
    )


# --- Routes -------------------------------------------------------------------

@router.get("/patients", response_model=PatientListOut)
def patients_list(search: str = "", filtre: str = "tous",
                  limit: Optional[int] = 20, offset: int = 0) -> PatientListOut:
    with core.db() as conn:
        items = repo.list_patients(conn, search=search, filtre=filtre,
                                   limit=limit, offset=offset)
        total = repo.count_patients(conn, search=search, filtre=filtre)
    return PatientListOut(items=[patient_out(p) for p in items], total=total)


@router.get("/patients/{patient_id}", response_model=PatientDetailOut)
def patient_detail(patient_id: int) -> PatientDetailOut:
    with core.db() as conn:
        p = repo.get_patient(conn, patient_id)
        if p is None:
            raise core.ApiError(core.ERR_NOT_FOUND,
                                f"Patient introuvable : {patient_id}", status=404)
        du, enc, reste = repo.solde_patient(conn, patient_id)
        nb_docs = repo.count_documents_for_patient(conn, patient_id)
        nb_enc = repo.count_encaissements_patient(conn, patient_id)
        has_sent = repo.patient_has_sent_document(conn, patient_id)
        a_regler = repo.list_prestations_a_regler(conn, patient_id)
    return PatientDetailOut(
        patient=patient_out(p),
        solde=SoldeOut(du=du, encaisse=enc, reste=reste),
        nb_documents=nb_docs, nb_encaissements=nb_enc, has_sent=has_sent,
        nb_actes_a_regler=len(a_regler),
        total_a_regler=sum(pr.reste for pr in a_regler),
    )


@router.post("/patients/match", response_model=MatchOut)
def patients_match(body: PatientIn) -> MatchOut:
    with core.db() as conn:
        matches = repo.find_matches(conn, body.nom, body.prenom)
    return MatchOut(matches=[patient_out(p) for p in matches])


@router.post("/patients", response_model=PatientOut,
             responses={409: {"model": DuplicateWarning}})
def patients_create(body: PatientIn) -> PatientOut:
    if not (body.nom or "").strip() or not (body.prenom or "").strip():
        raise core.ApiError(core.ERR_VALIDATION,
                            "Le nom et le prénom sont obligatoires.", status=400)
    try:
        with core.db() as conn:
            if not body.force:
                matches = repo.find_matches(conn, body.nom, body.prenom)
                if matches:
                    m = matches[0]
                    raise core.ApiError(
                        "DUPLICATE_PATIENT",
                        f"Un patient « {m.display} » (#{m.id}) existe déjà.",
                        status=409,
                    )
            p = repo.create_patient(conn, _to_patient(body))
            repo.log_audit(conn, "fiche_creee", {"display": p.display},
                           patient_id=p.id)
        return patient_out(p)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.put("/patients/{patient_id}", response_model=PatientOut)
def patients_update(patient_id: int, body: PatientIn) -> PatientOut:
    try:
        with core.db() as conn:
            existing = repo.get_patient(conn, patient_id)
            if existing is None:
                raise core.ApiError(core.ERR_NOT_FOUND,
                                    f"Patient introuvable : {patient_id}", status=404)
            p = _to_patient(body, patient_id)
            changed = repo.update_patient(conn, p)
            repo.log_audit(conn, "fiche_modifiee", {"champs": changed},
                           patient_id=patient_id)
            p = repo.get_patient(conn, patient_id)
        return patient_out(p)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)
