"""Tests métier pour `crm.rappels` : validation, transitions, idempotence.

Utilise la DB de test (`conftest.test_db`) pour `validate_rappel` et les
fonctions repo sous-jacentes (vérif patient / numéro WhatsApp), et une DB en
mémoire pour les transitions atomiques via `traiter_rappels_dus`.

Couvre les cas :
- Validation (type, titre, échéance, patient requis, numéro WhatsApp requis,
  message obligatoire pour message_patient).
- Traitement des rappels dus : transition planifie → du / a_envoyer.
- Idempotence : rejouer `traiter_rappels_dus` ne re-traite rien.
"""
import sqlite3

import pytest

from crm import rappels as rappels_logic
from crm import repo

# -----------------------------------------------------------------------------
# Fixtures locales : DB en mémoire indépendante pour les tests de transition,
# sans dépendre de l'état global de `conftest.test_db`.
# -----------------------------------------------------------------------------


@pytest.fixture
def mem_db():
    """Une DB SQLite en mémoire avec le schéma complet (via crm.db.connect)."""

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # On réutilise le schéma de production via executescript.
    from crm.db import _SCHEMA

    conn.executescript(_SCHEMA)
    yield conn
    conn.close()


def _create_patient_with_whatsapp(
    conn, nom="Dupont", prenom="Jean", phone="0612345678"
):
    """Crée un patient + un numéro marqué WhatsApp (pré-requis message_patient)."""
    p = repo.create_patient(
        conn,
        repo.Patient(
            id=None,
            nom=nom,
            prenom=prenom,
            telephones=[
                repo.PatientPhone(
                    id=None, patient_id=0, telephone=phone, relation="Lui-même",
                    is_whatsapp=True,
                )
            ],
        ),
    )
    return p


# =============================================================================
# validate_rappel
# =============================================================================


class TestValidateRappel:
    def test_alerte_interne_ok(self, test_db):
        """Une alerte interne valide ne lève pas (patient optionnel)."""
        rappels_logic.validate_rappel(
            test_db,
            type_rappel="alerte_interne",
            patient_id=None,
            message=None,
            titre="Relancer le fournisseur",
            echeance="2026-12-31",
        )

    def test_type_invalide(self, test_db):
        with pytest.raises(rappels_logic.RappelValidationError):
            rappels_logic.validate_rappel(
                test_db,
                type_rappel="inconnu",
                patient_id=None,
                message=None,
                titre="Titre",
                echeance="2026-12-31",
            )

    def test_titre_vide(self, test_db):
        with pytest.raises(rappels_logic.RappelValidationError):
            rappels_logic.validate_rappel(
                test_db,
                type_rappel="alerte_interne",
                patient_id=None,
                message=None,
                titre="   ",
                echeance="2026-12-31",
            )

    def test_echeance_vide(self, test_db):
        with pytest.raises(rappels_logic.RappelValidationError):
            rappels_logic.validate_rappel(
                test_db,
                type_rappel="alerte_interne",
                patient_id=None,
                message=None,
                titre="Titre",
                echeance="",
            )

    def test_message_patient_sans_patient(self, test_db):
        with pytest.raises(rappels_logic.RappelValidationError):
            rappels_logic.validate_rappel(
                test_db,
                type_rappel="message_patient",
                patient_id=None,
                message="Bonjour",
                titre="RDV",
                echeance="2026-12-31",
            )

    def test_message_patient_patient_inexistant(self, test_db):
        with pytest.raises(rappels_logic.RappelValidationError):
            rappels_logic.validate_rappel(
                test_db,
                type_rappel="message_patient",
                patient_id=999999,
                message="Bonjour",
                titre="RDV",
                echeance="2026-12-31",
            )

    def test_message_patient_sans_numero_whatsapp(self, test_db):
        """Patient sans numéro marqué WhatsApp → rejet."""
        p = repo.create_patient(
            test_db,
            repo.Patient(
                id=None,
                nom="Sans",
                prenom="Wa",
                telephones=[
                    repo.PatientPhone(
                        id=None, patient_id=0, telephone="0612345678",
                        relation="Lui-même", is_whatsapp=False,
                    )
                ],
            ),
        )
        with pytest.raises(rappels_logic.RappelValidationError):
            rappels_logic.validate_rappel(
                test_db,
                type_rappel="message_patient",
                patient_id=p.id,
                message="Bonjour",
                titre="RDV",
                echeance="2026-12-31",
            )

    def test_message_patient_sans_message(self, test_db):
        p = _create_patient_with_whatsapp(test_db)
        with pytest.raises(rappels_logic.RappelValidationError):
            rappels_logic.validate_rappel(
                test_db,
                type_rappel="message_patient",
                patient_id=p.id,
                message="",
                titre="RDV",
                echeance="2026-12-31",
            )

    def test_message_patient_ok(self, test_db):
        """message_patient valide (patient + numéro WhatsApp + message)."""
        p = _create_patient_with_whatsapp(test_db)
        rappels_logic.validate_rappel(
            test_db,
            type_rappel="message_patient",
            patient_id=p.id,
            message="Bonjour, RDV le lundi",
            titre="Rappel RDV",
            echeance="2026-12-31",
        )


# =============================================================================
# get_whatsapp_link_for_rappel
# =============================================================================


class TestWhatsAppLinkForRappel:
    def test_alerte_pas_de_lien(self, test_db):
        """Un rappel alerte_interne ne peut pas générer de lien wa.me."""
        r = repo.create_rappel(
            test_db,
            repo.Rappel(
                id=None, type="alerte_interne", titre="T", echeance="2026-12-31",
            ),
        )
        with pytest.raises(ValueError):
            rappels_logic.get_whatsapp_link_for_rappel(test_db, r)

    def test_message_patient_lien(self, test_db):
        p = _create_patient_with_whatsapp(test_db, phone="98765432")
        r = repo.create_rappel(
            test_db,
            repo.Rappel(
                id=None, type="message_patient", titre="RDV", echeance="2026-12-31",
                patient_id=p.id, message="Bonjour",
            ),
        )
        url = rappels_logic.get_whatsapp_link_for_rappel(test_db, r)
        assert url.startswith("https://wa.me/")
        assert "21698765432" in url
        assert "Bonjour" in url


# =============================================================================
# traiter_rappels_dus — transitions + idempotence (DB en mémoire isolée)
# =============================================================================


def _insert_rappel(conn, type_, echeance, etat="planifie"):
    """Insère un rappel directement (contourne create_rappel qui force 'planifie')."""
    conn.execute(
        """INSERT INTO rappels (type, titre, echeance, etat, lu, created_at)
           VALUES (?, ?, ?, ?, 0, datetime('now'))""",
        (type_, f"Test {type_}", echeance, etat),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM rappels ORDER BY id DESC LIMIT 1").fetchone()
    return repo._row_to_rappel(row)


class TestTraiterRappelsDus:
    def test_aucun_du(self, mem_db):
        """Sans rappel échu, rien n'est traité."""
        traites = rappels_logic.traiter_rappels_dus(mem_db)
        assert traites == []

    def test_planifie_echu_alerte_passe_du(self, mem_db):
        """Une alerte planifiée échue → transition vers 'du'."""
        # Échéance dans le passé
        r = _insert_rappel(mem_db, "alerte_interne", "2020-01-01 00:00:00")
        traites = rappels_logic.traiter_rappels_dus(mem_db)
        assert len(traites) == 1
        assert traites[0].id == r.id
        assert traites[0].etat == "du"
        assert traites[0].notified_at is not None

    def test_planifie_echu_message_passe_a_envoyer(self, mem_db):
        """Un message_patient planifié échu → transition vers 'a_envoyer'."""
        _insert_rappel(mem_db, "message_patient", "2020-01-01 00:00:00")
        traites = rappels_logic.traiter_rappels_dus(mem_db)
        assert len(traites) == 1
        assert traites[0].etat == "a_envoyer"

    def test_planifie_futur_non_traite(self, mem_db):
        """Un rappel planifié avec échéance future n'est pas traité."""
        _insert_rappel(mem_db, "alerte_interne", "2099-12-31 23:59:59")
        traites = rappels_logic.traiter_rappels_dus(mem_db)
        assert traites == []

    def test_idempotence_rejeu(self, mem_db):
        """Rejouer traiter_rappels_dus ne re-traite pas les rappels déjà dus."""
        r = _insert_rappel(mem_db, "alerte_interne", "2020-01-01 00:00:00")
        # Premier traitement
        traites = rappels_logic.traiter_rappels_dus(mem_db)
        assert len(traites) == 1
        # Deuxième traitement : le rappel n'est plus 'planifie', ignoré
        traites2 = rappels_logic.traiter_rappels_dus(mem_db)
        assert traites2 == []
        # L'état n'a pas changé entre les deux passes
        final = repo.get_rappel(mem_db, r.id)
        assert final.etat == "du"

    def test_rappel_deja_traite_ignore(self, mem_db):
        """Un rappel déjà dans un état non-planifie est ignoré."""
        for etat in ("du", "a_envoyer", "envoye", "traite", "annule"):
            _insert_rappel(mem_db, "alerte_interne", "2020-01-01 00:00:00", etat=etat)
        traites = rappels_logic.traiter_rappels_dus(mem_db)
        assert traites == []

    def test_plusieurs_dus_tous_traites(self, mem_db):
        """N rappels en retard → N transitions, une par rappel."""
        for _ in range(5):
            _insert_rappel(mem_db, "alerte_interne", "2020-01-01 00:00:00")
        traites = rappels_logic.traiter_rappels_dus(mem_db)
        assert len(traites) == 5
        assert all(t.etat == "du" for t in traites)

    def test_echeance_aujourdhui_depassee(self, mem_db):
        """Un rappel dont l'échéance est aujourd'hui (passée) est dû.

        Garde-fou contre une régression UTC vs localtime : si la comparaison
        utilisait `datetime('now')` (UTC) contre une `echeance` en heure locale,
        le test reste valide car on utilise une heure précise dans le passé
        d'aujourd'hui. L'essentiel est que la borne locale soit cohérente.
        """
        from datetime import datetime

        echeance = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        r = _insert_rappel(mem_db, "alerte_interne", echeance)
        traites = rappels_logic.traiter_rappels_dus(mem_db)
        assert any(t.id == r.id for t in traites)


# =============================================================================
# Garde d'état sur marquer_rappel_envoye (un rappel terminal ne ressuscite pas)
# =============================================================================


class TestMarquerRappelEnvoyeGuard:
    def test_depuis_a_envoyer_ok(self, mem_db):
        """Depuis 'a_envoyer' (état actif) → transition vers 'envoye' autorisée."""
        r = _insert_rappel(
            mem_db, "message_patient", "2020-01-01 00:00:00", etat="a_envoyer"
        )
        updated = repo.marquer_rappel_envoye(mem_db, r.id)
        assert updated.etat == "envoye"
        assert updated.sent_at is not None

    def test_depuis_traite_refuse(self, mem_db):
        """Un rappel déjà 'traite' (terminal) ne peut pas redevenir 'envoye'."""
        r = _insert_rappel(
            mem_db, "message_patient", "2020-01-01 00:00:00", etat="traite"
        )
        updated = repo.marquer_rappel_envoye(mem_db, r.id)
        # Inchangé : toujours 'traite'
        assert updated.etat == "traite"
        assert updated.sent_at is None

    def test_depuis_annule_refuse(self, mem_db):
        """Un rappel annulé ne peut pas être marqué envoyé."""
        r = _insert_rappel(
            mem_db, "message_patient", "2020-01-01 00:00:00", etat="annule"
        )
        updated = repo.marquer_rappel_envoye(mem_db, r.id)
        assert updated.etat == "annule"
        assert updated.sent_at is None

    def test_depuis_envoye_idempotent(self, mem_db):
        """Marquer envoyé un rappel déjà envoyé → inchangé (pas de re-timestamp)."""
        r = _insert_rappel(
            mem_db, "message_patient", "2020-01-01 00:00:00", etat="envoye"
        )
        updated = repo.marquer_rappel_envoye(mem_db, r.id)
        assert updated.etat == "envoye"

    def test_rappel_inexistant_renvoie_none(self, mem_db):
        assert repo.marquer_rappel_envoye(mem_db, 999999) is None
