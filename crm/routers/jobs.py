"""Routeur jobs (ecran Travaux) : liste des lots, detail ligne-par-patient,
lots de generation/envoi et relance des erreurs.

Un lot cree une ligne **persistante** `jobs` (visible dans Travaux) ET diffuse sa
progression en **SSE** : la ligne repo est creee synchronement (pour naviguer vers
le detail) puis deroulee dans le worker serialise avec une connexion dediee
(calque `_launch_job`/`runner` de l'app Flet).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from crm import generator, repo, server as core
from crm.db import connect as db_connect

router = APIRouter(prefix="/api", tags=["jobs"])


# --- Modeles ------------------------------------------------------------------

class JobOut(BaseModel):
    id: int
    kind: str
    doc_type: str
    statut: str
    total: int
    done: int
    ok: int
    skipped: int
    errors: int
    created_at: Optional[str] = None
    finished_at: Optional[str] = None


class JobItemOut(BaseModel):
    id: int
    patient_id: Optional[int] = None
    patient_display: Optional[str] = None
    document_id: Optional[int] = None
    statut: str
    message: Optional[str] = None
    has_file: bool = False


class JobListOut(BaseModel):
    items: list[JobOut]
    total: int


class JobDetailOut(BaseModel):
    job: JobOut
    items: list[JobItemOut]


class BatchIn(BaseModel):
    kind: str                       # 'generation' | 'envoi'
    document_ids: list[int]
    mailjet_template_id: Optional[int] = None


class BatchAcceptedOut(BaseModel):
    job_id: str       # identifiant SSE (progression)
    repo_job_id: int  # ligne `jobs` persistante


def job_out(j: repo.Job) -> JobOut:
    return JobOut(id=j.id, kind=j.kind, doc_type=j.doc_type, statut=j.statut,
                  total=j.total, done=j.done, ok=j.ok, skipped=j.skipped,
                  errors=j.errors, created_at=j.created_at, finished_at=j.finished_at)


# --- Lecture ------------------------------------------------------------------

@router.get("/jobs", response_model=JobListOut)
def jobs_list(date_from: str = "", date_to: str = "", limit: Optional[int] = 20,
              offset: int = 0) -> JobListOut:
    with core.db() as conn:
        items = repo.list_jobs(conn, limit=limit, offset=offset,
                               date_from=date_from, date_to=date_to)
        total = repo.count_jobs(conn, date_from=date_from, date_to=date_to)
    return JobListOut(items=[job_out(j) for j in items], total=total)


@router.get("/jobs/{job_id}", response_model=JobDetailOut)
def job_detail(job_id: int) -> JobDetailOut:
    with core.db() as conn:
        job = repo.get_job(conn, job_id)
        if job is None:
            raise core.ApiError(core.ERR_NOT_FOUND, f"Job introuvable : {job_id}",
                                status=404)
        rows = repo.list_job_items(conn, job_id)
        out_items: list[JobItemOut] = []
        for it in rows:
            display = None
            has_file = False
            if it.patient_id:
                p = repo.get_patient(conn, it.patient_id)
                display = p.display if p else None
            if it.document_id:
                d = repo.get_document(conn, it.document_id)
                has_file = bool(d and d.file_path and Path(d.file_path).exists())
            out_items.append(JobItemOut(
                id=it.id, patient_id=it.patient_id, patient_display=display,
                document_id=it.document_id, statut=it.statut, message=it.message,
                has_file=has_file))
    return JobDetailOut(job=job_out(job), items=out_items)


# --- Lots (generation / envoi) ------------------------------------------------

def _run_batch_job(repo_job_id: int, kind: str, document_ids: list[int],
                   mailjet_template_id: Optional[int]):
    """Fabrique la tache worker qui deroule un lot par documents (calque `runner`)."""

    def task(report):
        conn = db_connect()
        config = None
        if kind == "envoi":
            from src.config import load_config
            config = load_config()
        total = len(document_ids)
        try:
            for i, did in enumerate(document_ids):
                try:
                    d = repo.get_document(conn, did)
                    if d is None:
                        repo.add_job_item(conn, repo_job_id, None, "skip",
                                          document_id=did,
                                          message="Document introuvable.")
                    else:
                        try:
                            if kind == "generation":
                                generator.render_document(conn, d)
                            else:
                                generator.send_document(conn, d, config,
                                                        template_id=mailjet_template_id)
                            repo.add_job_item(conn, repo_job_id, d.patient_id, "ok",
                                              document_id=d.id)
                        except Exception as exc:  # noqa: BLE001
                            repo.add_job_item(conn, repo_job_id, d.patient_id, "erreur",
                                              document_id=d.id, message=str(exc))
                except Exception as exc:  # noqa: BLE001
                    try:
                        repo.add_job_item(conn, repo_job_id, None, "erreur",
                                          document_id=did, message=str(exc))
                    except Exception:  # noqa: BLE001
                        pass
                report((i + 1) / total if total else 1.0, f"{i + 1}/{total} traité(s)")
            final = repo.get_job(conn, repo_job_id)
            if final and final.errors:
                statut = "termine_partiel" if final.ok else "erreur"
            else:
                statut = "termine"
            repo.finish_job(conn, repo_job_id, statut)
            return {"job_id": repo_job_id, "statut": statut}
        except Exception:  # noqa: BLE001
            try:
                repo.finish_job(conn, repo_job_id, "erreur")
            except Exception:  # noqa: BLE001
                pass
            raise
        finally:
            conn.close()

    return task


@router.post("/documents/batch", response_model=BatchAcceptedOut, status_code=202)
def documents_batch(body: BatchIn) -> BatchAcceptedOut:
    if body.kind not in ("generation", "envoi"):
        raise core.ApiError(core.ERR_VALIDATION, "Type de lot inconnu.", status=400)
    ids = list(dict.fromkeys(body.document_ids))  # dedup en preservant l'ordre
    if not ids:
        raise core.ApiError(core.ERR_VALIDATION, "Aucun document sélectionné.",
                            status=400)
    mailjet_template_id = body.mailjet_template_id
    with core.db() as conn:
        first = repo.get_document(conn, ids[0])
        doc_type = first.type if first else "documents"
        if body.kind == "envoi" and mailjet_template_id is None:
            default = repo.get_default_mail_template(conn)
            mailjet_template_id = default.mailjet_template_id if default else None
        params = json.dumps({"mode": "documents",
                             "mailjet_template_id": mailjet_template_id},
                            ensure_ascii=False)
        job = repo.create_job(conn, body.kind, doc_type, len(ids), params)
        repo.log_audit(conn, f"job_{body.kind}",
                       f"job #{job.id} {doc_type} — {len(ids)} élément(s)")
    task = _run_batch_job(job.id, body.kind, ids, mailjet_template_id)
    return BatchAcceptedOut(job_id=core.submit_job(task), repo_job_id=job.id)


@router.post("/jobs/{job_id}/relaunch", response_model=BatchAcceptedOut, status_code=202)
def job_relaunch(job_id: int) -> BatchAcceptedOut:
    """Relance les documents en erreur d'un job (nouveau lot)."""
    with core.db() as conn:
        job = repo.get_job(conn, job_id)
        if job is None:
            raise core.ApiError(core.ERR_NOT_FOUND, f"Job introuvable : {job_id}",
                                status=404)
        failed = repo.list_failed_job_items(conn, job_id)
        ids = [it.document_id for it in failed if it.document_id]
        if not ids:
            raise core.ApiError(core.ERR_VALIDATION,
                                "Aucune erreur à relancer pour ce job.", status=400)
        mailjet_template_id = None
        if job.kind == "envoi":
            default = repo.get_default_mail_template(conn)
            mailjet_template_id = default.mailjet_template_id if default else None
        params = json.dumps({"mode": "documents", "relance_de": job_id},
                            ensure_ascii=False)
        new_job = repo.create_job(conn, job.kind, job.doc_type, len(ids), params)
        repo.log_audit(conn, f"job_{job.kind}",
                       f"job #{new_job.id} (relance #{job_id}) — {len(ids)} élément(s)")
    task = _run_batch_job(new_job.id, job.kind, ids, mailjet_template_id)
    return BatchAcceptedOut(job_id=core.submit_job(task), repo_job_id=new_job.id)
