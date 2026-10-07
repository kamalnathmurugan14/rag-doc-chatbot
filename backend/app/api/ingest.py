from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.session import connect
from app.errors import AppError

router = APIRouter()


class IngestIn(BaseModel):
    force: bool = False
    paths: list[str] | None = None


@router.post("/ingest", status_code=202)
def ingest(request: Request, body: IngestIn | None = None):
    body = body or IngestIn()
    job_id = request.app.state.container.ingestion.start(body.force, body.paths)
    if job_id is None:
        return JSONResponse(
            {"error": {"code": "INGEST_RUNNING", "message": "An ingestion job is already running"}}, status_code=409
        )
    return {"job_id": job_id}


@router.get("/ingest/status")
def status(request: Request) -> dict:
    c = request.app.state.container
    return {**c.ingestion.status(), "indexed_chunks": c.store.count()}


@router.delete("/index")
def clear_index(request: Request, confirm: bool = False) -> dict:
    c = request.app.state.container
    if not confirm:
        raise AppError("CONFIRM_REQUIRED", "Pass ?confirm=true to delete the whole index", 400)
    if c.ingestion.status()["state"] == "running":
        raise AppError("INGEST_RUNNING", "Wait for the running ingestion job to finish", 409)
    c.ingestion.clear()
    return {"cleared": True}


@router.get("/files")
def files(request: Request) -> dict:
    with connect(request.app.state.container.settings.db_path) as con:
        rows = con.execute(
            "SELECT rel_path, status, n_chunks, error, indexed_at FROM files ORDER BY rel_path"
        ).fetchall()
    return {"files": [dict(r) for r in rows]}
