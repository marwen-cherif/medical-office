import pytest
from httpx import ASGITransport, AsyncClient

from crm import repo
from crm.server import app


@pytest.mark.asyncio
async def test_dashboard_empty(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get("/api/dashboard", headers=headers)
        assert response.status_code == 200
        data = response.json()
        kpis = data["kpis"]
        assert kpis["ca_encaisse"] == 0.0
        assert kpis["encours"] == 0.0
        assert kpis["nb_patients"] == 0
        assert kpis["nb_documents"] == 0
        assert isinstance(data["documents_by_type"], list)
        assert isinstance(data["recent_activity"], list)


@pytest.mark.asyncio
async def test_dashboard_with_data(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    repo.create_paiement(
        test_db,
        repo.Paiement(
            id=None,
            patient_id=p.id,
            montant=300.0,
            montant_regle=300.0,
            statut="encaisse",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get("/api/dashboard", headers=headers)
        assert response.status_code == 200
        data = response.json()
        kpis = data["kpis"]
        assert kpis["nb_patients"] == 1
        assert kpis["nb_paiements_encaisses"] >= 1


@pytest.mark.asyncio
async def test_dashboard_date_filter(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get(
            "/api/dashboard?date_from=2020-01-01&date_to=2020-12-31",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["kpis"]["nb_patients"] == 0
