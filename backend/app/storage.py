import shutil
from pathlib import Path

from app.config import get_settings


def analysis_dir(analysis_id: str) -> Path:
    return get_settings().data_dir / "analyses" / analysis_id


def save_upload(analysis_id: str, name: str, data: bytes) -> Path:
    folder = analysis_dir(analysis_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(data)
    return path


def artifact_path(analysis_id: str, relative: str) -> Path | None:
    base = (analysis_dir(analysis_id) / "artifacts").resolve()
    target = (base / relative).resolve()
    if base not in target.parents or not target.is_file():
        return None
    return target


def remove(analysis_id: str) -> None:
    shutil.rmtree(analysis_dir(analysis_id), ignore_errors=True)
