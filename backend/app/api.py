import hashlib
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import jobs, storage
from app.config import get_settings
from app.db import get_session
from app.forensics.ingest import UnsupportedFile, sniff
from app.llm import ChatClient
from app.models import Analysis
from app.schemas import AnalysisDetail, AnalysisPage, AnalysisSummary, Health

router = APIRouter(prefix="/api")

EXTENSIONS = {"pdf": ".pdf", "docx": ".docx"}
CONTENT_TYPES = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", llm_enabled=ChatClient(get_settings()).enabled)


def _get(session: Session, analysis_id: str) -> Analysis:
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return analysis


@router.post("/analyses", response_model=AnalysisSummary, status_code=status.HTTP_201_CREATED)
async def create_analysis(file: UploadFile = File(...), session: Session = Depends(get_session)) -> Analysis:
    settings = get_settings()
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is empty.")
    if len(data) > limit:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Files must be {settings.max_upload_mb} MB or smaller.")
    try:
        kind = sniff(data)
    except UnsupportedFile as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    filename = Path(file.filename or "upload").name[:255]
    suffix = EXTENSIONS.get(kind) or Path(filename).suffix.lower() or ".bin"
    content_type = CONTENT_TYPES.get(kind) or file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    analysis = Analysis(
        id=str(uuid.uuid4()),
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        stored_name=f"original{suffix}",
        status="queued",
    )
    storage.save_upload(analysis.id, analysis.stored_name, data)
    session.add(analysis)
    session.commit()
    jobs.enqueue(analysis.id)
    session.refresh(analysis)
    return analysis


@router.get("/analyses", response_model=AnalysisPage)
def list_analyses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=200),
    session: Session = Depends(get_session),
) -> AnalysisPage:
    query = select(Analysis)
    if q:
        query = query.where(Analysis.filename.ilike(f"%{q}%"))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = session.scalars(
        query.order_by(Analysis.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AnalysisPage(
        items=[AnalysisSummary.model_validate(a) for a in items], total=total, page=page, page_size=page_size
    )


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(analysis_id: str, session: Session = Depends(get_session)) -> Analysis:
    return _get(session, analysis_id)


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: str, session: Session = Depends(get_session)) -> Response:
    analysis = _get(session, analysis_id)
    session.delete(analysis)
    session.commit()
    storage.remove(analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/analyses/{analysis_id}/files/{path:path}")
def get_file(analysis_id: str, path: str, session: Session = Depends(get_session)) -> FileResponse:
    _get(session, analysis_id)
    target = storage.artifact_path(analysis_id, path)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return FileResponse(target, headers={"Cache-Control": "private, max-age=86400"})
