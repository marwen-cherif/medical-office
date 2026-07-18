import pytest
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient

from crm import repo
from crm.server import app


@pytest.mark.asyncio
async def test_jobs_list_empty(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/jobs", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["items"] == []


@pytest.mark.asyncio
async def test_jobs_list_with_data(test_db):
    repo.create_job(test_db, "generation", "facture", 5, "{}")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/jobs", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["kind"] == "generation"
        assert data["items"][0]["doc_type"] == "facture"


@pytest.mark.asyncio
async def test_job_detail(test_db):
    job = repo.create_job(test_db, "generation", "facture", 3, "{}")
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    repo.add_job_item(test_db, job.id, p.id, "ok", message="OK")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(f"/api/jobs/{job.id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["job"]["id"] == job.id
        assert len(data["items"]) == 1
        assert data["items"][0]["patient_display"] is not None


@pytest.mark.asyncio
async def test_job_detail_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get("/api/jobs/99999", headers=headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_documents_batch_invalid_kind(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/documents/batch",
            json={"kind": "invalide", "document_ids": [1]},
            headers=headers,
        )
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_documents_batch_empty_ids(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(
            "/api/documents/batch",
            json={"kind": "generation", "document_ids": []},
            headers=headers,
        )
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_documents_batch_generation(test_db):
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    doc = repo.create_document(
        test_db,
        repo.Document(
            id=None,
            patient_id=p.id,
            type="facture",
            template="facture",
            statut="brouillon",
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}

        with patch("crm.server.submit_job", return_value="mock-job-id"):
            res = await client.post(
                "/api/documents/batch",
                json={"kind": "generation", "document_ids": [doc.id]},
                headers=headers,
            )
            assert res.status_code == 202
            data = res.json()
            assert data["job_id"] == "mock-job-id"
            assert data["repo_job_id"] is not None


@pytest.mark.asyncio
async def test_job_relaunch_not_found(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post("/api/jobs/99999/relaunch", headers=headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_job_relaunch_no_errors(test_db):
    job = repo.create_job(test_db, "generation", "facture", 1, "{}")
    p = repo.create_patient(
        test_db, repo.Patient(id=None, nom="Dupont", prenom="Jean")
    )
    repo.add_job_item(test_db, job.id, p.id, "ok", message="OK")
    repo.finish_job(test_db, job.id, "termine")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.post(f"/api/jobs/{job.id}/relaunch", headers=headers)
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_jobs_list_date_filter(test_db):
    repo.create_job(test_db, "generation", "facture", 1, "{}")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        res = await client.get(
            "/api/jobs?date_from=2020-01-01&date_to=2020-12-31",
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
