from __future__ import annotations

from typing import Any

from app.agent.workspace import ToolResult, Workspace

BOX = {
    "type": "array",
    "items": {"type": "number"},
    "description": "[x, y, width, height] as fractions 0..1 of the page",
}
IDS = {"type": "array", "items": {"type": "string"}, "description": "word ids such as p1w12"}
CATEGORIES = ["typography", "ink", "sharpness", "alignment", "digits", "copy_move", "compression", "noise",
              "metadata", "structure", "semantic"]


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


SUBMIT = _fn(
    "submit_report",
    "Finish the investigation with your verdict and evidence-backed findings.",
    {
        "verdict": {"type": "string", "enum": ["likely_authentic", "suspicious", "highly_risky"]},
        "summary": {"type": "string", "description": "2-4 plain sentences for a reviewer"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string", "description": "what differs and why it matters, with numbers"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low", "info"]},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "page": {"type": "integer"},
                    "word_ids": IDS,
                    "box": BOX,
                    "evidence": {"type": "object", "description": "measured values, e.g. {\"width_px\": 96, \"peer_median_px\": 93}"},
                },
                "required": ["title", "detail", "severity", "category"],
            },
        },
    },
    ["verdict", "summary", "findings"],
)

TOOLS = [
    _fn("view_page", "See a whole page image.", {"page": {"type": "integer"}}, ["page"]),
    _fn("zoom", "See a magnified region of a page to inspect glyph shapes, edges and backgrounds.",
        {"page": {"type": "integer"}, "box": BOX}, ["page", "box"]),
    _fn("read_text", "Read OCR lines with word ids for a page (use when the overview was truncated).",
        {"page": {"type": "integer"}, "start": {"type": "integer"}, "count": {"type": "integer"}}, ["page"]),
    _fn("measure", "Measure typography of words: stroke width, weight, stroke contrast, size, width, ink, sharpness.",
        {"word_ids": IDS}, ["word_ids"]),
    _fn("compare", "Compare target words against fair peers feature by feature; reports which features stand out.",
        {"target_ids": IDS, "peer_ids": IDS}, ["target_ids", "peer_ids"]),
    _fn("find_peers", "Suggest fair peers for a word: same line, same colour and size, same number format.",
        {"word_id": {"type": "string"}}, ["word_id"]),
    _fn("digit_widths", "List widths of all formatted numbers (dates, amounts, IDs) on a page, grouped by format.",
        {"page": {"type": "integer"}}, ["page"]),
    _fn("region_forensics", "Pixel forensics for a region: compression level, background grain and copy-move matches vs the page.",
        {"page": {"type": "integer"}, "box": BOX}, ["page", "box"]),
    _fn("validate", "Check ID numbers and dates in a text snippet: PAN format, Aadhaar and GSTIN checksums, impossible dates.",
        {"text": {"type": "string"}}, ["text"]),
    SUBMIT,
]


def dispatch(workspace: Workspace, name: str, args: dict[str, Any]) -> ToolResult:
    handlers = {
        "view_page": lambda a: workspace.view_page(int(a["page"])),
        "zoom": lambda a: workspace.zoom(int(a["page"]), list(a["box"])),
        "read_text": lambda a: workspace.read_text(int(a["page"]), int(a.get("start", 0)), int(a.get("count", 80))),
        "measure": lambda a: workspace.measure(list(a["word_ids"])),
        "compare": lambda a: workspace.compare(list(a["target_ids"]), list(a["peer_ids"])),
        "find_peers": lambda a: workspace.find_peers(str(a["word_id"])),
        "digit_widths": lambda a: workspace.digit_widths(int(a["page"])),
        "region_forensics": lambda a: workspace.region_forensics(int(a["page"]), list(a["box"])),
        "validate": lambda a: workspace.validate(str(a["text"])),
    }
    if name not in handlers:
        raise ValueError(f"unknown tool {name}")
    return handlers[name](args)
