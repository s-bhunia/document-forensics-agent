import logging
from datetime import datetime, timezone

from redis import Redis
from rq import Queue

from app.agent import Investigator
from app.config import get_settings
from app.db import session_factory
from app.forensics import analyze_file
from app.llm import ChatClient
from app.models import Analysis
from app.storage import analysis_dir

log = logging.getLogger(__name__)
QUEUE_NAME = "analyses"


def run_analysis(analysis_id: str) -> None:
    settings = get_settings()
    with session_factory()() as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            return
        analysis.status = "processing"
        session.commit()
        try:
            folder = analysis_dir(analysis_id)
            raw = (folder / analysis.stored_name).read_bytes()
            client = ChatClient(settings)
            investigator = (
                Investigator(client, max_steps=settings.agent_max_steps, max_images=settings.agent_max_images)
                if client.enabled
                else None
            )
            result = analyze_file(raw, folder / "artifacts", lang=settings.ocr_lang, investigator=investigator)
            analysis.result = result
            analysis.risk_score = result["risk_score"]
            analysis.label = result["label"]
            analysis.finding_count = len(result["findings"])
            analysis.status = "completed"
        except Exception as exc:
            log.exception("Analysis %s failed", analysis_id)
            analysis.status = "failed"
            analysis.error = str(exc)[:500] or exc.__class__.__name__
        analysis.completed_at = datetime.now(timezone.utc)
        session.commit()


def enqueue(analysis_id: str) -> None:
    settings = get_settings()
    if settings.inline_jobs:
        run_analysis(analysis_id)
        return
    queue = Queue(QUEUE_NAME, connection=Redis.from_url(settings.redis_url))
    queue.enqueue(run_analysis, analysis_id, job_timeout=settings.job_timeout, result_ttl=3600, failure_ttl=86400)
