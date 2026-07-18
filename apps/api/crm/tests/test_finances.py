import pytest
from httpx import ASGITransport, AsyncClient

from crm import repo
from crm.server import app


@pytest.mark.asyncio
async def test_finances_paiements_empty(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get("/api/finances/paiements", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert (
            "Total" in data["summary"]["label"]
            or "recouvrer" in data["summary"]["label"]
        )


@pytest.mark.asyncio
async def test_finances_paiements_flow(test_db):
    # Populate test data
    # 1. Create Patient
    p1 = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )

    # 2. Create unpaid document / creance via a payment in 'regle_partiellement' status
    repo.create_paiement(
        test_db,
        repo.Paiement(
            id=None,
            patient_id=p1.id,
            montant=150.0,
            montant_regle=50.0,
            statut="regle_partiellement",
            notes="Note de creance",
        ),
    )

    # 3. Create paid payment
    repo.create_paiement(
        test_db,
        repo.Paiement(
            id=None,
            patient_id=p1.id,
            montant=200.0,
            montant_regle=200.0,
            statut="encaisse",
            notes="Paiement fait",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}

        # Test GET /api/finances/paiements?statut=en_attente
        response = await client.get(
            "/api/finances/paiements?statut=en_attente", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        creance_items = [item for item in data["items"] if item["kind"] == "creance"]
        assert len(creance_items) >= 1
        assert creance_items[0]["montant"] == 150.0
        assert creance_items[0]["reste"] == 100.0

        # Test GET /api/finances/paiements?statut=encaisse
        response = await client.get(
            "/api/finances/paiements?statut=encaisse", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        paiement_items = [item for item in data["items"] if item["kind"] == "paiement"]
        assert len(paiement_items) >= 1
        assert paiement_items[0]["montant"] == 200.0
        assert paiement_items[0]["reste"] == 0.0


@pytest.mark.asyncio
async def test_depenses_and_prestataires_flow(test_db):
    # 1. Create a Prestataire
    pr = repo.create_prestataire(
        test_db,
        repo.Prestataire(
            id=None, nom="Fournisseur A", prenom="Alain", email="fourn@test.com"
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}

        # Create a depense via POST /api/depenses
        dep_data = {
            "prestataire_id": pr.id,
            "montant": 500.0,
            "montant_regle": 100.0,
            "libelle": "Achat matériel",
            "notes": "Facture Janvier",
        }
        res_create = await client.post("/api/depenses", json=dep_data, headers=headers)
        assert res_create.status_code == 200
        dep_res = res_create.json()
        dep_id = dep_res["id"]
        assert dep_res["montant"] == 500.0
        assert dep_res["montant_regle"] == 100.0
        assert dep_res["reste"] == 400.0
        assert dep_res["statut"] == "regle_partiellement"

        # Test GET /api/finances/depenses
        res_list = await client.get(
            "/api/finances/depenses?statut=tous", headers=headers
        )
        assert res_list.status_code == 200
        data = res_list.json()
        assert data["total"] == 1
        assert data["items"][0]["depense"]["id"] == dep_id
        assert data["items"][0]["prestataire_display"] == "FOURNISSEUR A Alain"
        assert data["summary"]["du"] == 500.0
        assert data["summary"]["regle"] == 100.0
        assert data["summary"]["reste"] == 400.0

        # Test GET /api/prestataires/{id}/depenses
        res_pr_dep = await client.get(
            f"/api/prestataires/{pr.id}/depenses", headers=headers
        )
        assert res_pr_dep.status_code == 200
        data_pr_dep = res_pr_dep.json()
        assert data_pr_dep["total"] == 1
        assert data_pr_dep["items"][0]["id"] == dep_id

        # Add a payment reglement: POST /api/depenses/{id}/reglement
        reg_data = {"versement": 150.0, "mode": "carte", "motif": "Deuxième acompte"}
        res_reg = await client.post(
            f"/api/depenses/{dep_id}/reglement", json=reg_data, headers=headers
        )
        assert res_reg.status_code == 200
        dep_res_updated = res_reg.json()
        assert dep_res_updated["montant_regle"] == 250.0
        assert dep_res_updated["reste"] == 250.0

        # Test GET /api/depenses/{id}/reglements
        res_regs = await client.get(
            f"/api/depenses/{dep_id}/reglements", headers=headers
        )
        assert res_regs.status_code == 200
        regs_list = res_regs.json()
        assert len(regs_list) == 2
        assert regs_list[0]["montant"] == 150.0
        assert regs_list[0]["mode"] == "carte"
        assert regs_list[0]["motif"] == "Deuxième acompte"

        # Test GET /api/prestataires/{id}/reglements
        res_pr_regs = await client.get(
            f"/api/prestataires/{pr.id}/reglements", headers=headers
        )
        assert res_pr_regs.status_code == 200
        pr_regs_list = res_pr_regs.json()
        assert pr_regs_list["total"] == 2
        assert pr_regs_list["items"][0]["depense_id"] == dep_id

        # Delete depense: DELETE /api/depenses/{id}
        res_del = await client.delete(f"/api/depenses/{dep_id}", headers=headers)
        assert res_del.status_code == 200

        # Check it's deleted
        res_list_after = await client.get(
            "/api/finances/depenses?statut=tous", headers=headers
        )
        assert res_list_after.json()["total"] == 0
