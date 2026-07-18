"""Logique métier des rappels datés.

Ce module est importé par :
- `crm/routers/rappels.py`  (API backend FastAPI)
- `crm/service.py`          (processus de fond headless)

Il ne dépend que de `crm/repo.py` et `crm/db.py` — pas de Flet, pas de Word,
pas de Mailjet.

Responsabilités :
  2.1  Sélection des rappels dus + transition atomique planifie → du/a_envoyer
  2.2  Normalisation du numéro de téléphone au format international
  2.3  Construction du lien WhatsApp wa.me
  2.4  Validation à la création (message_patient : patient + numéro WhatsApp requis)
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from . import repo
from .phones import (
    DEFAULT_COUNTRY_CODE,
    build_whatsapp_link,
    normalize_phone,
)

# =============================================================================
# 2.2 / 2.3 — Normalisation & lien WhatsApp
# =============================================================================
# La logique de normalisation E.164 et de construction du lien wa.me est
# partagée avec `crm/generator.py` via `crm/phones.py` (source unique de vérité,
# testée unitairement). Réexportée ici pour la compat ascendante des appelants
# qui importent depuis `crm.rappels`.
__all__ = [
    "build_whatsapp_link",
    "normalize_phone",
    "validate_rappel",
    "traiter_rappels_dus",
    "get_default_country",
    "get_whatsapp_link_for_rappel",
    "RappelValidationError",
]


# =============================================================================
# 2.4 — Validation à la création
# =============================================================================


class RappelValidationError(ValueError):
    """Erreur métier à la création/édition d'un rappel."""

    pass


def validate_rappel(
    conn: sqlite3.Connection,
    type_rappel: str,
    patient_id: Optional[int],
    message: Optional[str],
    titre: str,
    echeance: str,
) -> None:
    """Valide les données d'un rappel avant création ou modification.

    Règles :
    - `type` doit être 'alerte_interne' ou 'message_patient'.
    - `titre` ne peut pas être vide.
    - `echeance` ne peut pas être vide.
    - Pour `message_patient` :
        · Un `patient_id` valide est obligatoire.
        · Le patient doit avoir au moins un numéro `is_whatsapp = 1`.
        · Un `message` non vide est obligatoire.

    Lève `RappelValidationError` au premier problème rencontré.
    """
    if type_rappel not in repo.RAPPEL_TYPES:
        raise RappelValidationError(
            f"Type de rappel invalide : « {type_rappel} ». "
            f"Valeurs acceptées : {', '.join(sorted(repo.RAPPEL_TYPES))}."
        )

    if not titre or not titre.strip():
        raise RappelValidationError("Le titre du rappel est obligatoire.")

    if not echeance or not echeance.strip():
        raise RappelValidationError("L'échéance du rappel est obligatoire.")

    if type_rappel == "message_patient":
        if patient_id is None:
            raise RappelValidationError(
                "Un rappel de type « message patient » exige un patient rattaché."
            )

        patient = repo.get_patient(conn, patient_id)
        if patient is None:
            raise RappelValidationError(f"Patient introuvable (id={patient_id}).")

        wa_phones = repo.list_whatsapp_phones(conn, patient_id)
        if not wa_phones:
            raise RappelValidationError(
                f"Le patient « {patient.display} » n'a aucun numéro WhatsApp "
                "utilisable (aucun numéro marqué WhatsApp dans sa fiche)."
            )

        if not message or not message.strip():
            raise RappelValidationError(
                "Le texte du message est obligatoire pour un rappel « message patient »."
            )


# =============================================================================
# 2.1 — Traitement des rappels dus (transition atomique + idempotence)
# =============================================================================


def traiter_rappels_dus(conn: sqlite3.Connection) -> list[repo.Rappel]:
    """Traite tous les rappels planifiés dont l'échéance est dépassée.

    Pour chaque rappel trouvé (état 'planifie' ET echeance <= maintenant) :
    - Effectue la transition atomique planifie → du (alerte_interne)
                                       ou planifie → a_envoyer (message_patient)
    - Horodate `notified_at`.

    Idempotence : seuls les rappels à l'état 'planifie' sont sélectionnés
    (cf. `repo.list_rappels_dus`). Un rappel déjà dans un état ultérieur est
    ignoré même si la tâche planifiée se rejoue.

    Renvoie la liste des rappels effectivement mis à jour (état modifié).
    """
    dus = repo.list_rappels_dus(conn)
    traites: list[repo.Rappel] = []
    for r in dus:
        updated = repo.marquer_rappel_notifie(conn, r.id, r.type)
        if updated is not None and updated.etat != "planifie":
            traites.append(updated)
    return traites


# =============================================================================
# Utilitaires
# =============================================================================


def get_default_country(conn: sqlite3.Connection) -> str:
    """Lit l'indicatif pays par défaut depuis `meta` (clé rappels_default_country).

    Retourne DEFAULT_COUNTRY_CODE si non configuré.
    """
    val = repo.get_setting(conn, "rappels_default_country")
    return (val or DEFAULT_COUNTRY_CODE).strip() or DEFAULT_COUNTRY_CODE


def get_whatsapp_link_for_rappel(
    conn: sqlite3.Connection,
    rappel: repo.Rappel,
    phone_id: Optional[int] = None,
) -> str:
    """Construit le lien wa.me pour un rappel de type message_patient.

    Si `phone_id` est fourni, utilise ce numéro spécifique ; sinon utilise le
    premier numéro is_whatsapp=1 du patient.

    Lève `ValueError` si le rappel n'est pas de type message_patient, si aucun
    numéro WhatsApp n'est disponible, ou si le numéro ne peut être normalisé.
    """
    if rappel.type != "message_patient":
        raise ValueError(
            "Construction d'un lien wa.me impossible : le rappel n'est pas "
            "de type « message_patient »."
        )
    if rappel.patient_id is None:
        raise ValueError(
            "Construction d'un lien wa.me impossible : aucun patient rattaché."
        )

    country_code = get_default_country(conn)

    if phone_id is not None:
        # Numéro spécifique demandé par le frontend (sélecteur multi-numéros)
        row = conn.execute(
            "SELECT * FROM patient_phones WHERE id = ? AND patient_id = ? AND is_whatsapp = 1",
            (phone_id, rappel.patient_id),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Numéro WhatsApp id={phone_id} introuvable pour ce patient."
            )
        phone = row["telephone"]
    else:
        wa_phones = repo.list_whatsapp_phones(conn, rappel.patient_id)
        if not wa_phones:
            raise ValueError("Aucun numéro WhatsApp disponible pour ce patient.")
        phone = wa_phones[0].telephone

    return build_whatsapp_link(phone, rappel.message or "", country_code)
