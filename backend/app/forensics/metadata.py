from __future__ import annotations

from datetime import datetime

from PIL import ExifTags, Image

from app.forensics.types import Category, Finding, Severity

EDITING_TOOLS = (
    "photoshop", "gimp", "lightroom", "snapseed", "picsart", "canva", "pixlr", "affinity", "paint.net",
    "fotor", "inkscape", "illustrator", "coreldraw", "ilovepdf", "smallpdf", "sejda", "pdfescape",
    "pdf-xchange", "phantompdf", "nitro", "soda pdf", "pdffiller", "dochub", "pdf editor", "foxit",
    "wondershare", "pdfelement", "libreoffice draw",
)


def editing_tool(value: str | None) -> str | None:
    if not value:
        return None
    lower = value.lower()
    return next((tool for tool in EDITING_TOOLS if tool in lower), None)


def _exif_date(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%Y:%m:%d %H:%M:%S") if value else None
    except ValueError:
        return None


def image_metadata(img: Image.Image) -> tuple[dict[str, str], list[Finding]]:
    meta: dict[str, str] = {"format": img.format or "unknown", "size": f"{img.width}x{img.height}", "mode": img.mode}
    findings: list[Finding] = []
    exif = img.getexif()
    tags = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
    try:
        tags.update({ExifTags.TAGS.get(k, str(k)): v for k, v in exif.get_ifd(ExifTags.IFD.Exif).items()})
    except Exception:
        pass
    for key in ("Make", "Model", "Software", "DateTime", "DateTimeOriginal", "Artist"):
        if key in tags and str(tags[key]).strip():
            meta[key] = str(tags[key]).strip("\x00 ").strip()

    tool = editing_tool(meta.get("Software"))
    if tool:
        findings.append(
            Finding(
                category=Category.METADATA,
                severity=Severity.MEDIUM,
                title="Saved by image-editing software",
                detail=f"The file's metadata names “{meta['Software']}”, an editing tool, as the last software to save it.",
                evidence={"software": meta["Software"]},
            )
        )
    original, modified = _exif_date(meta.get("DateTimeOriginal")), _exif_date(meta.get("DateTime"))
    if original and modified and (modified - original).total_seconds() > 120:
        findings.append(
            Finding(
                category=Category.METADATA,
                severity=Severity.LOW,
                title="Image modified after capture",
                detail=f"Captured {original:%d %b %Y %H:%M} but last saved {modified:%d %b %Y %H:%M}.",
                evidence={"captured": str(original), "modified": str(modified)},
            )
        )
    if not exif:
        meta["exif"] = "none"
    return meta, findings
