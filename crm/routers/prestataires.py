"""Routeur prestataires : fiches fournisseurs, factures importees, depenses.

Reutilise `crm/repo.py` + `crm/generator.import_facture` sans les modifier.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from crm import generator, repo, server as core

router = APIRouter(prefix="/api", tags=["prestataires"])


# --- Modeles ------------------------------------------------------------------

class PrestataireOut(BaseModel):
    id: int
    nom: str
    prenom: str
    display: str
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None


class PrestataireIn(BaseModel):
    nom: str
    prenom: str = ""
    email: Optional[str] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    notes: Optional[str] = None
    force: bool = False


class SummaryOut(BaseModel):
    du: float
    regle: float
    reste: float


class PrestataireListOut(BaseModel):
    items: list[PrestataireOut]
    total: int


class PrestataireDetailOut(BaseModel):
    prestataire: PrestataireOut
    summary: SummaryOut
    nb_factures: int
    nb_depenses: int


class MatchOut(BaseModel):
    matches: list[PrestataireOut]


class FactureOut(BaseModel):
    id: int
    prestataire_id: int
    fichier: str
    nom_original: Optional[str] = None
    montant: Optional[float] = None
    libelle: Optional[str] = None
    created_at: Optional[str] = None


class FactureListOut(BaseModel):
    items: list[FactureOut]
    total: int


class FactureIaDisponibleOut(BaseModel):
    """Indique si l'extraction IA du montant de facture est configurée."""
    disponible: bool


class FactureIaMontantOut(BaseModel):
    """Montant TTC lu par IA (pré-remplissage éditable) ; `montant` null si non trouvé."""
    disponible: bool
    montant: Optional[float] = None


class DepenseOut(BaseModel):
    id: int
    prestataire_id: int
    facture_id: Optional[int] = None
    montant: float
    montant_regle: float
    reste: float
    statut: str
    mode: Optional[str] = None
    motif: Optional[str] = None
    libelle: Optional[str] = None
    date_echeance: Optional[str] = None
    date_paiement: Optional[str] = None
    created_at: Optional[str] = None


class DepenseListOut(BaseModel):
    items: list[DepenseOut]
    total: int


class DepenseIn(BaseModel):
    prestataire_id: int
    montant: float
    montant_regle: float = 0.0
    motif: Optional[str] = None
    libelle: Optional[str] = None
    date_echeance: Optional[str] = None
    mode: Optional[str] = None
    notes: Optional[str] = None
    facture_id: Optional[int] = None  # lie la depense a une facture importee


class ReglementDepenseIn(BaseModel):
    versement: float
    mode: Optional[str] = None
    motif: Optional[str] = None
    date_reglement: Optional[str] = None


# --- Serialisation ------------------------------------------------------------

def prestataire_out(p: repo.Prestataire) -> PrestataireOut:
    return PrestataireOut(id=p.id, nom=p.nom, prenom=p.prenom, display=p.display,
                          email=p.email, telephone=p.telephone, adresse=p.adresse,
                          notes=p.notes)


def facture_out(f: repo.Facture) -> FactureOut:
    return FactureOut(id=f.id, prestataire_id=f.prestataire_id, fichier=f.fichier,
                      nom_original=f.nom_original, montant=f.montant,
                      libelle=f.libelle, created_at=f.created_at)


def depense_out(d: repo.Depense) -> DepenseOut:
    return DepenseOut(id=d.id, prestataire_id=d.prestataire_id, facture_id=d.facture_id,
                      montant=d.montant, montant_regle=d.montant_regle, reste=d.reste,
                      statut=d.statut, mode=d.mode, motif=d.motif, libelle=d.libelle,
                      date_echeance=d.date_echeance, date_paiement=d.date_paiement,
                      created_at=d.created_at)


def _to_prestataire(body: PrestataireIn, pid: Optional[int] = None) -> repo.Prestataire:
    return repo.Prestataire(id=pid, nom=body.nom.strip(),
                            prenom=(body.prenom or "").strip(),
                            email=body.email or None, telephone=body.telephone or None,
                            adresse=body.adresse or None, notes=body.notes or None)


# --- Prestataires -------------------------------------------------------------

@router.get("/prestataires", response_model=PrestataireListOut)
def prestataires_list(search: str = "", limit: Optional[int] = 20,
                      offset: int = 0) -> PrestataireListOut:
    with core.db() as conn:
        items = repo.list_prestataires(conn, search=search, limit=limit, offset=offset)
        total = repo.count_prestataires(conn, search=search)
    return PrestataireListOut(items=[prestataire_out(p) for p in items], total=total)


@router.get("/prestataires/{prestataire_id}", response_model=PrestataireDetailOut)
def prestataire_detail(prestataire_id: int) -> PrestataireDetailOut:
    with core.db() as conn:
        p = repo.get_prestataire(conn, prestataire_id)
        if p is None:
            raise core.ApiError(core.ERR_NOT_FOUND,
                                f"Prestataire introuvable : {prestataire_id}",
                                status=404)
        nb_fac = repo.count_factures_for_prestataire(conn, prestataire_id)
        nb_dep = repo.count_depenses_for_prestataire(conn, prestataire_id)
        all_dep = repo.list_depenses(conn, prestataire_id)
        du = sum(d.montant for d in all_dep)
        regle = sum(d.montant_regle for d in all_dep)
    return PrestataireDetailOut(
        prestataire=prestataire_out(p),
        summary=SummaryOut(du=du, regle=regle, reste=max(0.0, du - regle)),
        nb_factures=nb_fac, nb_depenses=nb_dep)


@router.post("/prestataires/match", response_model=MatchOut)
def prestataires_match(body: PrestataireIn) -> MatchOut:
    with core.db() as conn:
        matches = repo.find_prestataire_matches(conn, body.nom, body.prenom)
    return MatchOut(matches=[prestataire_out(p) for p in matches])


@router.post("/prestataires", response_model=PrestataireOut,
             responses={409: {"model": MatchOut}})
def prestataires_create(body: PrestataireIn) -> PrestataireOut:
    if not (body.nom or "").strip():
        raise core.ApiError(core.ERR_VALIDATION,
                            "Le nom / la raison sociale est obligatoire.", status=400)
    try:
        with core.db() as conn:
            if not body.force:
                matches = repo.find_prestataire_matches(conn, body.nom, body.prenom)
                if matches:
                    m = matches[0]
                    raise core.ApiError(
                        "DUPLICATE_PRESTATAIRE",
                        f"Un prestataire « {m.display} » (#{m.id}) existe déjà.",
                        status=409)
            p = repo.create_prestataire(conn, _to_prestataire(body))
            repo.log_audit(conn, "prestataire_cree", {"display": p.display})
        return prestataire_out(p)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.put("/prestataires/{prestataire_id}", response_model=PrestataireOut)
def prestataires_update(prestataire_id: int, body: PrestataireIn) -> PrestataireOut:
    try:
        with core.db() as conn:
            existing = repo.get_prestataire(conn, prestataire_id)
            if existing is None:
                raise core.ApiError(core.ERR_NOT_FOUND,
                                    f"Prestataire introuvable : {prestataire_id}",
                                    status=404)
            repo.update_prestataire(conn, _to_prestataire(body, prestataire_id))
            repo.log_audit(conn, "prestataire_modifie", {"id": prestataire_id})
            p = repo.get_prestataire(conn, prestataire_id)
        return prestataire_out(p)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


# --- Factures -----------------------------------------------------------------

@router.get("/prestataires/{prestataire_id}/factures", response_model=FactureListOut)
def factures_list(prestataire_id: int, limit: Optional[int] = 20,
                  offset: int = 0) -> FactureListOut:
    with core.db() as conn:
        items = repo.list_factures(conn, prestataire_id, limit=limit, offset=offset)
        total = repo.count_factures_for_prestataire(conn, prestataire_id)
    return FactureListOut(items=[facture_out(f) for f in items], total=total)


@router.post("/prestataires/{prestataire_id}/factures", response_model=FactureOut)
async def facture_import(prestataire_id: int, file: UploadFile = File(...),
                         montant: Optional[float] = Form(None),
                         libelle: Optional[str] = Form(None)) -> FactureOut:
    """Importe (archive) une facture fournisseur uploadee."""
    data = await file.read()
    suffix = Path(file.filename or "facture").suffix or ".pdf"
    tmp = Path(tempfile.gettempdir()) / f"crm_import_{file.filename or 'facture'}"
    if not tmp.suffix:
        tmp = tmp.with_suffix(suffix)
    try:
        tmp.write_bytes(data)
        with core.db() as conn:
            p = repo.get_prestataire(conn, prestataire_id)
            if p is None:
                raise core.ApiError(core.ERR_NOT_FOUND,
                                    f"Prestataire introuvable : {prestataire_id}",
                                    status=404)
            fac = generator.import_facture(conn, p, tmp, montant=montant,
                                           libelle=libelle)
            repo.log_audit(conn, "facture_importee",
                           {"facture_id": fac.id, "prestataire_id": prestataire_id})
        return facture_out(fac)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


# --- Extraction IA du montant (pre-remplissage, vision) -----------------------
#
# Porte la fonctionnalite de l'oracle Flet (`_import_facture_dialog`) : a l'ouverture
# du dialogue d'import, le montant TTC est lu sur le scan par IA puis pre-rempli dans
# un champ EDITABLE (jamais auto-valide). Reutilise le moteur `src/ai` sans le modifier.
# Aucun secret ne transite : seul le montant lu est renvoye.

def _facture_ia_cfg_provider():
    """Config + provider IA de la feature 'facture_montant', ou (None, None) si IA off.

    Indisponible = config.ini absent, fonctionnalite absente/desactivee, provider
    inconnu ou cle d'API vide (cf. `provider_for_feature`). Ne leve jamais.
    """
    try:
        from src.ai.factory import provider_for_feature
        from src.config import load_config
        cfg = load_config()
        return cfg, provider_for_feature(cfg, "facture_montant")
    except Exception:  # noqa: BLE001 -- config.ini absent / IA non configuree
        return None, None


@router.get("/factures/ia-disponible", response_model=FactureIaDisponibleOut)
def facture_ia_disponible() -> FactureIaDisponibleOut:
    """Indique si l'extraction IA du montant de facture est configuree (vision)."""
    _, provider = _facture_ia_cfg_provider()
    return FactureIaDisponibleOut(disponible=provider is not None)


@router.post("/factures/ia-montant", response_model=FactureIaMontantOut)
async def facture_ia_montant(file: UploadFile = File(...)) -> FactureIaMontantOut:
    """Lit le montant TTC d'une facture scannee par IA (pre-remplissage editable).

    Ne cree / n'archive rien : renvoie seulement le montant lu (ou null). L'extraction
    ne leve jamais (repli null si IA off / format inconnu / echec).
    """
    cfg, provider = _facture_ia_cfg_provider()
    if cfg is None or provider is None:
        return FactureIaMontantOut(disponible=False, montant=None)
    data = await file.read()
    suffix = Path(file.filename or "facture").suffix or ".pdf"
    tmp = Path(tempfile.gettempdir()) / f"crm_ia_{file.filename or 'facture'}"
    if not tmp.suffix:
        tmp = tmp.with_suffix(suffix)
    try:
        tmp.write_bytes(data)
        from src.ai.features.facture_montant import extract_facture_montant
        montant = extract_facture_montant(cfg, tmp)  # ne leve jamais (None en repli)
        return FactureIaMontantOut(disponible=True, montant=montant)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


@router.post("/factures/{facture_id}/open", response_model=core.OkOut)
def facture_open(facture_id: int) -> core.OkOut:
    """Ouvre la facture archivée avec l'application par défaut (côté machine serveur,
    = poste de l'utilisateur). Calque `_open_path` de l'app Flet et `open_document`."""
    with core.db() as conn:
        fac = repo.get_facture(conn, facture_id)
    if fac is None or not fac.fichier:
        raise core.ApiError(core.ERR_NOT_FOUND, "Facture introuvable.", status=404)
    path = Path(fac.fichier)
    if not path.exists():
        raise core.ApiError(core.ERR_NOT_FOUND,
                            "Le fichier n'existe plus sur le disque.", status=404)
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:  # pragma: no cover
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:  # noqa: BLE001
        raise core.ApiError(core.ERR_VALIDATION, f"Ouverture impossible : {exc}")
    return core.OkOut()


@router.delete("/factures/{facture_id}", response_model=core.OkOut)
def facture_delete(facture_id: int) -> core.OkOut:
    with core.db() as conn:
        fac = repo.get_facture(conn, facture_id)
        if fac is None:
            raise core.ApiError(core.ERR_NOT_FOUND, "Facture introuvable.", status=404)
        if fac.fichier:
            try:
                p = Path(fac.fichier)
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        repo.delete_facture(conn, facture_id)
        repo.log_audit(conn, "facture_supprimee", {"facture_id": facture_id})
    return core.OkOut()


# --- Depenses -----------------------------------------------------------------

@router.get("/prestataires/{prestataire_id}/depenses", response_model=DepenseListOut)
def depenses_list(prestataire_id: int, limit: Optional[int] = 20,
                  offset: int = 0) -> DepenseListOut:
    with core.db() as conn:
        items = repo.list_depenses(conn, prestataire_id, limit=limit, offset=offset)
        total = repo.count_depenses_for_prestataire(conn, prestataire_id)
    return DepenseListOut(items=[depense_out(d) for d in items], total=total)


@router.post("/depenses", response_model=DepenseOut)
def depense_create(body: DepenseIn) -> DepenseOut:
    try:
        with core.db() as conn:
            dep = repo.create_depense(
                conn, body.prestataire_id, body.montant,
                montant_regle=body.montant_regle, motif=body.motif,
                facture_id=body.facture_id,
                date_echeance=body.date_echeance, mode=body.mode,
                libelle=body.libelle, notes=body.notes)
            repo.log_audit(conn, "depense_creee",
                           {"depense_id": dep.id, "montant": dep.montant})
        return depense_out(dep)
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.post("/depenses/{depense_id}/reglement", response_model=DepenseOut)
def depense_reglement(depense_id: int, body: ReglementDepenseIn) -> DepenseOut:
    try:
        with core.db() as conn:
            existing = repo.get_depense(conn, depense_id)
            if existing is None:
                raise core.ApiError(core.ERR_NOT_FOUND, "Dépense introuvable.",
                                    status=404)
            dep = repo.add_depense_reglement(conn, depense_id, body.versement,
                                             mode=body.mode, motif=body.motif,
                                             when=body.date_reglement)
            repo.log_audit(conn, "depense_reglee",
                           {"depense_id": depense_id, "versement": body.versement})
        return depense_out(dep)
    except core.ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise core._err_from_engine(exc)


@router.delete("/depenses/{depense_id}", response_model=core.OkOut)
def depense_delete(depense_id: int) -> core.OkOut:
    with core.db() as conn:
        repo.delete_depense(conn, depense_id)
        repo.log_audit(conn, "depense_supprimee", {"depense_id": depense_id})
    return core.OkOut()
