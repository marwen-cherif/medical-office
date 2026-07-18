import pytest
from httpx import ASGITransport, AsyncClient

from crm import repo
from crm.server import app


@pytest.mark.asyncio
async def test_patients_list_empty(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get("/api/patients", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []


@pytest.mark.asyncio
async def test_patients_list_with_data(test_db):
    repo.create_patient(test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean"))
    repo.create_patient(test_db, repo.Patient(id=None, nom="Martin", prenom="Marie"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get("/api/patients", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_patients_list_search(test_db):
    repo.create_patient(test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean"))
    repo.create_patient(test_db, repo.Patient(id=None, nom="Martin", prenom="Marie"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get("/api/patients?search=Dupont", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["nom"] == "Dupont"


@pytest.mark.asyncio
async def test_patients_list_pagination(test_db):
    for i in range(5):
        repo.create_patient(
            test_db, repo.Patient(id=None, nom=f"Patient{i}", prenom=f"P{i}")
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get(
            "/api/patients?limit=2&offset=0", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_patient_detail(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get(f"/api/patients/{p.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["patient"]["id"] == p.id
        assert data["patient"]["nom"] == "Dupont"
        assert data["solde"]["du"] == 0.0
        assert data["nb_documents"] == 0


@pytest.mark.asyncio
async def test_patient_detail_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get("/api/patients/99999", headers=headers)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_patients_match(test_db):
    repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.post(
            "/api/patients/match",
            json={"nom": "Dupont", "prenom": "Jean"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matches"]) >= 1


@pytest.mark.asyncio
async def test_patients_create(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.post(
            "/api/patients",
            json={"nom": "Nouveau", "prenom": "Patient", "force": True},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["nom"] == "Nouveau"
        assert data["prenom"] == "Patient"
        assert data["id"] is not None


@pytest.mark.asyncio
async def test_patients_create_duplicate_detection(test_db):
    repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.post(
            "/api/patients",
            json={"nom": "Dupont", "prenom": "Jean"},
            headers=headers,
        )
        assert response.status_code == 409


@pytest.mark.asyncio
async def test_patients_create_force_duplicate(test_db):
    repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.post(
            "/api/patients",
            json={"nom": "Dupont", "prenom": "Jean", "force": True},
            headers=headers,
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_patients_create_validation_error(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.post(
            "/api/patients",
            json={"nom": "", "prenom": ""},
            headers=headers,
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_patients_update(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.put(
            f"/api/patients/{p.id}",
            json={"nom": "Durand", "prenom": "Pierre"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["nom"] == "Durand"
        assert data["prenom"] == "Pierre"


@pytest.mark.asyncio
async def test_patients_update_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.put(
            "/api/patients/99999",
            json={"nom": "Test", "prenom": "User"},
            headers=headers,
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_patients_create_with_telephones(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.post(
            "/api/patients",
            json={
                "nom": "Avec",
                "prenom": "Tel",
                "force": True,
                "telephones": [
                    {
                        "telephone": "0612345678",
                        "relation": "Lui-même",
                        "is_whatsapp": True,
                    }
                ],
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["telephones"]) == 1
        assert data["telephones"][0]["telephone"] == "0612345678"
        assert data["telephones"][0]["is_whatsapp"] is True
