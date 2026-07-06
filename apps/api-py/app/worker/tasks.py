from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.artifacts import generate_artifact
from app.services.documents import parse_document
from app.services.quality import run_quality_check
from app.worker.celery_app import celery_app


def with_session(handler):
    db: Session = SessionLocal()
    try:
        return handler(db)
    finally:
        db.close()


@celery_app.task
def parse_document_task(document_id: str, job_id: str | None = None) -> dict:
    return with_session(lambda db: parse_document(db, document_id, job_id) or {"status": "not_found"})


@celery_app.task
def export_artifact_task(artifact_id: str) -> dict:
    artifact = with_session(lambda db: generate_artifact(db, artifact_id))
    return {"id": artifact.id, "status": artifact.status} if artifact else {"status": "not_found"}


@celery_app.task
def quality_check_task(project_id: str) -> dict:
    return with_session(lambda db: run_quality_check(db, project_id))
