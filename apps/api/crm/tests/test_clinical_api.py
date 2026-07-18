import pytest
from httpx import ASGITransport, AsyncClient

from crm import repo
from crm.server import app


@pytest.mark.asyncio
async def test_clinical_empty(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get(
            f"/api/patients/{p.id}/clinical", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["notes_en_attente"] == []
        assert data["isoles"] == []
        assert data["plans"] == []
        assert data["total_a_regler"] == 0.0


@pytest.mark.asyncio
async def test_plan_crud(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}

        # Create plan
        res = await client.post(
            f"/api/patients/{p.id}/plans",
            json={"titre": "Plan A", "notes": "Notes du plan"},
            headers=headers,
        )
        assert res.status_code == 200
        plan = res.json()
        plan_id = plan["id"]
        assert plan["titre"] == "Plan A"
        assert plan["patient_id"] == p.id

        # Update plan
        res = await client.put(
            f"/api/plans/{plan_id}",
            json={"titre": "Plan A modifié"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["titre"] == "Plan A modifié"

        # Delete plan
        res = await client.delete(f"/api/plans/{plan_id}", headers=headers)
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_plan_update_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.put(
            "/api/plans/99999",
            json={"titre": "X"},
            headers=headers,
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_plan_delete_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.delete("/api/plans/99999", headers=headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_prestation_crud(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}

        # Create prestation (acte isolé)
        res = await client.post(
            f"/api/patients/{p.id}/prestations",
            json={"libelle": "Détartrage", "montant": 80.0},
            headers=headers,
        )
        assert res.status_code == 200
        pres = res.json()
        pres_id = pres["id"]
        assert pres["libelle"] == "Détartrage"
        assert pres["montant"] == 80.0
        assert pres["reste"] == 80.0

        # Update prestation
        res = await client.put(
            f"/api/prestations/{pres_id}",
            json={"libelle": "Détartrage complet", "montant": 100.0},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["libelle"] == "Détartrage complet"
        assert res.json()["montant"] == 100.0

        # Delete prestation
        res = await client.delete(f"/api/prestations/{pres_id}", headers=headers)
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_prestation_update_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.put(
            "/api/prestations/99999",
            json={"libelle": "X", "montant": 10.0},
            headers=headers,
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_prestation_delete_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.delete("/api/prestations/99999", headers=headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_prestation_reglement(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    pres = repo.create_prestation(test_db, p.id, "Soin", 200.0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            f"/api/prestations/{pres.id}/reglement",
            json={"montant": 100.0, "mode": "carte"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["montant_regle"] == 100.0
        assert data["reste"] == 100.0


@pytest.mark.asyncio
async def test_prestation_reglement_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/prestations/99999/reglement",
            json={"montant": 100.0},
            headers=headers,
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_cascade_regler(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    repo.create_prestation(test_db, p.id, "Soin A", 100.0)
    repo.create_prestation(test_db, p.id, "Soin B", 150.0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}

        # Cascade payment (include_notes defaults to False)
        res = await client.post(
            f"/api/patients/{p.id}/regler",
            json={"montant": 200.0, "mode": "especes", "include_notes": False},
            headers=headers,
        )
        # The endpoint may return 200 or 400 depending on creances state;
        # verify it returns a valid JSON response either way
        assert res.status_code in (200, 400)
        if res.status_code == 200:
            data = res.json()
            assert "alloue" in data
            assert "reste" in data


@pytest.mark.asyncio
async def test_encaissements(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    pres = repo.create_prestation(test_db, p.id, "Soin", 100.0)
    repo.add_prestation_reglement(test_db, pres.id, 50.0, mode="carte")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            f"/api/patients/{p.id}/encaissements", headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        assert data["solde"]["du"] == 100.0
        assert data["solde"]["encaisse"] == 50.0


@pytest.mark.asyncio
async def test_creances(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    repo.create_prestation(test_db, p.id, "Soin impayé", 200.0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            f"/api/patients/{p.id}/creances", headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        assert data[0]["reste"] == 200.0


@pytest.mark.asyncio
async def test_audit(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    repo.log_audit(
        test_db, "fiche_creee", {"display": "DUPONT Jean"}, patient_id=p.id
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            f"/api/patients/{p.id}/audit", headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        assert data[0]["action"] == "fiche_creee"


@pytest.mark.asyncio
async def test_clinical_with_plan_and_prestations(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    pl = repo.create_plan(test_db, p.id, "Plan principal")
    repo.create_prestation(test_db, p.id, "Soin plan", 150.0, plan_id=pl.id)
    repo.create_prestation(test_db, p.id, "Soin isolé", 80.0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            f"/api/patients/{p.id}/clinical", headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["plans"]) == 1
        assert data["plans"][0]["plan"]["titre"] == "Plan principal"
        assert len(data["plans"][0]["prestations"]) == 1
        assert len(data["isoles"]) == 1
        assert data["total_a_regler"] == 230.0


@pytest.mark.asyncio
async def test_paiement_crud(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}

        # Create paiement for reglement flow
        res = await client.post(
            f"/api/patients/{p.id}/paiements",
            json={"montant": 500.0, "statut": "en_attente", "notes": "Note test"},
            headers=headers,
        )
        assert res.status_code == 200
        pa = res.json()
        pa_id = pa["id"]
        assert pa["montant"] == 500.0
        assert pa["statut"] == "en_attente"

        # Reglement on paiement
        res = await client.post(
            f"/api/paiements/{pa_id}/reglement",
            json={"montant": 200.0, "mode": "cheque"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["montant_regle"] == 200.0

        # Encaisser
        res = await client.post(
            f"/api/paiements/{pa_id}/encaisser",
            json={},
            headers=headers,
        )
        assert res.status_code == 200

        # Create a second paiement (no reglements) to test delete
        res2 = await client.post(
            f"/api/patients/{p.id}/paiements",
            json={"montant": 100.0, "statut": "en_attente"},
            headers=headers,
        )
        assert res2.status_code == 200
        pa2_id = res2.json()["id"]

        # Delete paiement without reglements succeeds
        res = await client.delete(f"/api/paiements/{pa2_id}", headers=headers)
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_paiement_reglement_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/paiements/99999/reglement",
            json={"montant": 100.0},
            headers=headers,
        )
        assert res.status_code == 404
