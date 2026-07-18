import pytest
from httpx import ASGITransport, AsyncClient

from crm import repo
from crm.server import app


@pytest.mark.asyncio
async def test_prestataires_list_empty(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/prestataires", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["items"] == []


@pytest.mark.asyncio
async def test_prestataires_list_with_data(test_db):
    repo.create_prestataire(
        test_db,
        repo.Prestataire(id=None, nom="Fournisseur A", prenom="Alain"),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/prestataires", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1


@pytest.mark.asyncio
async def test_prestataires_search(test_db):
    repo.create_prestataire(
        test_db,
        repo.Prestataire(id=None, nom="Fournisseur A", prenom="Alain"),
    )
    repo.create_prestataire(
        test_db,
        repo.Prestataire(id=None, nom="Labo B", prenom="Bernard"),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            "/api/prestataires?search=Labo", headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1


@pytest.mark.asyncio
async def test_prestataire_detail(test_db):
    pr = repo.create_prestataire(
        test_db,
        repo.Prestataire(id=None, nom="Fournisseur A", prenom="Alain"),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(f"/api/prestataires/{pr.id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["prestataire"]["id"] == pr.id
        assert data["summary"]["du"] == 0.0
        assert data["nb_factures"] == 0
        assert data["nb_depenses"] == 0


@pytest.mark.asyncio
async def test_prestataire_detail_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/prestataires/99999", headers=headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_prestataires_match(test_db):
    repo.create_prestataire(
        test_db,
        repo.Prestataire(id=None, nom="Fournisseur A", prenom="Alain"),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/prestataires/match",
            json={"nom": "Fournisseur A", "prenom": "Alain"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["matches"]) >= 1


@pytest.mark.asyncio
async def test_prestataires_create(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/prestataires",
            json={"nom": "Nouveau", "prenom": "Fournisseur", "force": True},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["nom"] == "Nouveau"
        assert data["id"] is not None


@pytest.mark.asyncio
async def test_prestataires_create_duplicate_detection(test_db):
    repo.create_prestataire(
        test_db,
        repo.Prestataire(id=None, nom="Fournisseur A", prenom="Alain"),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/prestataires",
            json={"nom": "Fournisseur A", "prenom": "Alain"},
            headers=headers,
        )
        assert res.status_code == 409


@pytest.mark.asyncio
async def test_prestataires_create_validation_error(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/prestataires",
            json={"nom": "", "prenom": ""},
            headers=headers,
        )
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_prestataires_update(test_db):
    pr = repo.create_prestataire(
        test_db,
        repo.Prestataire(id=None, nom="Ancien", prenom="Nom"),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.put(
            f"/api/prestataires/{pr.id}",
            json={"nom": "Nouveau", "prenom": "Nom"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["nom"] == "Nouveau"


@pytest.mark.asyncio
async def test_prestataires_update_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.put(
            "/api/prestataires/99999",
            json={"nom": "Test"},
            headers=headers,
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_prestataire_depenses_flow(test_db):
    pr = repo.create_prestataire(
        test_db,
        repo.Prestataire(id=None, nom="Fournisseur", prenom="A"),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}

        # Create depense
        res = await client.post(
            "/api/depenses",
            json={
                "prestataire_id": pr.id,
                "montant": 500.0,
                "montant_regle": 100.0,
                "libelle": "Achat matériel",
            },
            headers=headers,
        )
        assert res.status_code == 200
        dep = res.json()
        dep_id = dep["id"]
        assert dep["montant"] == 500.0
        assert dep["reste"] == 400.0

        # List depenses for prestataire
        res = await client.get(
            f"/api/prestataires/{pr.id}/depenses", headers=headers
        )
        assert res.status_code == 200
        assert res.json()["total"] == 1

        # Add reglement
        res = await client.post(
            f"/api/depenses/{dep_id}/reglement",
            json={"versement": 150.0, "mode": "virement"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["montant_regle"] == 250.0

        # List reglements for depense
        res = await client.get(
            f"/api/depenses/{dep_id}/reglements", headers=headers
        )
        assert res.status_code == 200
        regs = res.json()
        assert len(regs) == 2

        # List reglements for prestataire
        res = await client.get(
            f"/api/prestataires/{pr.id}/reglements", headers=headers
        )
        assert res.status_code == 200
        assert res.json()["total"] == 2

        # Delete depense
        res = await client.delete(f"/api/depenses/{dep_id}", headers=headers)
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_depense_reglement_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/depenses/99999/reglement",
            json={"versement": 100.0},
            headers=headers,
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_facture_ia_disponible(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/factures/ia-disponible", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data["disponible"], bool)


@pytest.mark.asyncio
async def test_facture_delete_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.delete("/api/factures/99999", headers=headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_facture_open_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post("/api/factures/99999/open", headers=headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_prestataire_factures_list_empty(test_db):
    pr = repo.create_prestataire(
        test_db,
        repo.Prestataire(id=None, nom="Fournisseur", prenom="A"),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            f"/api/prestataires/{pr.id}/factures", headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["items"] == []
