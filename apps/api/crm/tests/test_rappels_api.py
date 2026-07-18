import pytest
from httpx import ASGITransport, AsyncClient

from crm import repo
from crm.server import app


def _create_patient_with_whatsapp(conn, nom="Dupont", prenom="Jean", phone="0612345678"):
    p = repo.create_patient(
        conn,
        repo.Patient(
            id=None,
            nom=nom,
            prenom=prenom,
            telephones=[
                repo.PatientPhone(
                    id=None,
                    patient_id=0,
                    telephone=phone,
                    relation="Lui-même",
                    is_whatsapp=True,
                )
            ],
        ),
    )
    return p


@pytest.mark.asyncio
async def test_rappels_create_alerte_interne(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/rappels",
            json={
                "type": "alerte_interne",
                "titre": "Rappeler le fournisseur",
                "echeance": "2099-12-31",
            },
            headers=headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["type"] == "alerte_interne"
        assert data["titre"] == "Rappeler le fournisseur"
        assert data["etat"] == "planifie"


@pytest.mark.asyncio
async def test_rappels_create_message_patient(test_db):
    p = _create_patient_with_whatsapp(test_db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/rappels",
            json={
                "type": "message_patient",
                "titre": "RDV dentaire",
                "echeance": "2099-12-31",
                "patient_id": p.id,
                "message": "Bonjour, rappel de votre RDV.",
            },
            headers=headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["type"] == "message_patient"
        assert data["patient_id"] == p.id


@pytest.mark.asyncio
async def test_rappels_create_invalid_type(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/rappels",
            json={
                "type": "invalide",
                "titre": "Test",
                "echeance": "2099-12-31",
            },
            headers=headers,
        )
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_rappels_list_empty(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/rappels", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["items"] == []


@pytest.mark.asyncio
async def test_rappels_list_with_data(test_db):
    repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="Rappel 1",
            echeance="2099-12-31",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/rappels", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1


@pytest.mark.asyncio
async def test_rappels_list_filter_etat(test_db):
    repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="Rappel planifié",
            echeance="2099-12-31",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            "/api/rappels?etat=planifie", headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1


@pytest.mark.asyncio
async def test_rappels_count_actifs(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/rappels/count-actifs", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 0


@pytest.mark.asyncio
async def test_rappels_get(test_db):
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="Test rappel",
            echeance="2099-12-31",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(f"/api/rappels/{r.id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["titre"] == "Test rappel"


@pytest.mark.asyncio
async def test_rappels_get_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/rappels/99999", headers=headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_rappels_update(test_db):
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="Ancien titre",
            echeance="2099-12-31",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.put(
            f"/api/rappels/{r.id}",
            json={
                "type": "alerte_interne",
                "titre": "Nouveau titre",
                "echeance": "2099-06-15",
            },
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["titre"] == "Nouveau titre"


@pytest.mark.asyncio
async def test_rappels_ignorer(test_db):
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="A ignorer",
            echeance="2020-01-01",
            etat="du",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.patch(
            f"/api/rappels/{r.id}/ignorer", headers=headers
        )
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_rappels_marquer_envoye(test_db):
    p = _create_patient_with_whatsapp(test_db)
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="message_patient",
            titre="A envoyer",
            echeance="2020-01-01",
            etat="a_envoyer",
            patient_id=p.id,
            message="Bonjour",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.patch(
            f"/api/rappels/{r.id}/envoye", headers=headers
        )
        assert res.status_code == 200
        assert res.json()["etat"] == "envoye"


@pytest.mark.asyncio
async def test_rappels_marquer_envoye_wrong_type(test_db):
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="Test",
            echeance="2020-01-01",
            etat="du",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.patch(
            f"/api/rappels/{r.id}/envoye", headers=headers
        )
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_rappels_marquer_traite(test_db):
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="A traiter",
            echeance="2020-01-01",
            etat="du",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.patch(
            f"/api/rappels/{r.id}/traite", headers=headers
        )
        assert res.status_code == 200
        assert res.json()["etat"] == "traite"


@pytest.mark.asyncio
async def test_rappels_annuler(test_db):
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="A annuler",
            echeance="2099-12-31",
            etat="planifie",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.patch(
            f"/api/rappels/{r.id}/annuler", headers=headers
        )
        assert res.status_code == 200
        assert res.json()["etat"] == "annule"


@pytest.mark.asyncio
async def test_rappels_annuler_terminal_state(test_db):
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="A traiter d'abord",
            echeance="2020-01-01",
        ),
    )
    # Transition to 'du' then 'traite' via repo
    repo.marquer_rappel_traite(test_db, r.id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.patch(
            f"/api/rappels/{r.id}/annuler", headers=headers
        )
        assert res.status_code == 409


@pytest.mark.asyncio
async def test_rappels_process_dus(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post("/api/rappels/process-dus", headers=headers)
        assert res.status_code == 200
        assert res.json()["processed"] >= 0


@pytest.mark.asyncio
async def test_rappels_whatsapp_link(test_db):
    p = _create_patient_with_whatsapp(test_db, phone="0612345678")
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="message_patient",
            titre="RDV",
            echeance="2099-12-31",
            patient_id=p.id,
            message="Bonjour, rappel RDV",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            f"/api/rappels/{r.id}/whatsapp-link", headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert "wa.me" in data["url"] or "api.whatsapp.com" in data["url"]


@pytest.mark.asyncio
async def test_rappels_whatsapp_link_wrong_type(test_db):
    r = repo.create_rappel(
        test_db,
        repo.Rappel(
            id=None,
            type="alerte_interne",
            titre="Test",
            echeance="2099-12-31",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            f"/api/rappels/{r.id}/whatsapp-link", headers=headers
        )
        assert res.status_code == 400
