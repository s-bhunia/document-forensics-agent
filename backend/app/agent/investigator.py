from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.agent.prompts import FINAL_NUDGE, NO_TOOL_NUDGE, SYSTEM_PROMPT
from app.agent.tools import CATEGORIES, SUBMIT, TOOLS, dispatch
from app.agent.workspace import Scan, Workspace
from app.forensics.types import Category, Finding, Severity, union_box

log = logging.getLogger(__name__)
MAX_OVERVIEW_PAGES = 3
TEXT_CATEGORIES = {Category.TYPOGRAPHY, Category.INK, Category.SHARPNESS, Category.ALIGNMENT, Category.DIGITS}
REGION_CATEGORIES = {Category.COMPRESSION, Category.NOISE, Category.COPY_MOVE}


def _overlaps(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


class Chat(Protocol):
    model: str

    def chat(self, messages: list[dict], tools: list[dict] | None = None, tool_choice: Any = None) -> dict: ...


@dataclass
class Investigation:
    verdict: str
    summary: str
    findings: list[Finding]
    steps: list[dict] = field(default_factory=list)
    model: str = ""
    usage: dict | None = None


def _args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _brief(name: str, args: dict) -> str:
    if name in ("measure",):
        return f"{len(args.get('word_ids', []))} words"
    if name == "compare":
        return f"{len(args.get('target_ids', []))} vs {len(args.get('peer_ids', []))} peers"
    return ", ".join(f"{k}={v}" for k, v in args.items() if k != "text")[:120] or args.get("text", "")[:80]


class Investigator:
    def __init__(self, client: Chat, max_steps: int = 24, max_images: int = 14):
        self.client = client
        self.max_steps = max_steps
        self.max_images = max_images

    def usage(self, pages: int) -> dict | None:
        report = getattr(self.client, "usage_report", None)
        return report(pages) if callable(report) else None

    def run(self, scan: Scan) -> Investigation:
        workspace = Workspace(scan)
        content: list[dict] = [{"type": "text", "text": workspace.overview()}]
        images_used = 0
        for page in scan.document.pages[:MAX_OVERVIEW_PAGES]:
            for label, url in workspace.view_page(page.number).images:
                content += [{"type": "text", "text": f"Image: {label}"}, {"type": "image_url", "image_url": {"url": url}}]
                images_used += 1
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]
        steps: list[dict] = []
        nudges = 0

        for step in range(self.max_steps + 1):
            final = step == self.max_steps
            if final:
                messages.append({"role": "user", "content": FINAL_NUDGE})
            reply = self.client.chat(messages, tools=[SUBMIT] if final else TOOLS)
            messages.append({k: v for k, v in reply.items() if v is not None})
            calls = reply.get("tool_calls") or []
            if not calls:
                nudges += 1
                if nudges > 2:
                    break
                messages.append({"role": "user", "content": NO_TOOL_NUDGE})
                continue

            pending: list[dict] = []
            for call in calls:
                name = call.get("function", {}).get("name", "")
                args = _args(call.get("function", {}).get("arguments"))
                if name == "submit_report":
                    report = self._report(workspace, args)
                    steps.append({"tool": name, "input": f"{len(report.findings)} findings", "ok": True})
                    report.steps, report.model = steps, self.client.model
                    report.usage = self.usage(len(scan.document.pages))
                    return report
                try:
                    result = dispatch(workspace, name, args)
                    text, ok = result.text, True
                    for label, url in result.images:
                        if images_used >= self.max_images:
                            text += "\n(image budget used up; rely on measurements)"
                            continue
                        pending += [{"type": "text", "text": f"Image: {label}"}, {"type": "image_url", "image_url": {"url": url}}]
                        images_used += 1
                except Exception as exc:
                    text, ok = f"Error: {exc}", False
                steps.append({"tool": name, "input": _brief(name, args), "ok": ok})
                messages.append({"role": "tool", "tool_call_id": call.get("id", name), "content": text})
            if pending:
                messages.append({"role": "user", "content": pending})

        raise RuntimeError("investigation ended without a report")

    def _report(self, workspace: Workspace, args: dict) -> Investigation:
        verdict = str(args.get("verdict") or "suspicious")
        if verdict not in ("likely_authentic", "suspicious", "highly_risky"):
            verdict = "suspicious"
        findings: list[Finding] = []
        for item in args.get("findings") or []:
            finding = self._finding(workspace, item)
            if finding is not None:
                findings.append(finding)
        return Investigation(verdict=verdict, summary=str(args.get("summary") or "").strip()[:1200], findings=findings)

    @staticmethod
    def _grounded(workspace: Workspace, category: Category, ids: list[str], page_no: int | None, box) -> bool:
        if category in TEXT_CATEGORIES:
            return bool(ids) and all(i in workspace.measured for i in ids)
        if category in REGION_CATEGORIES:
            return box is not None and any(p == page_no and _overlaps(r, box) for p, r in workspace.regions)
        if category in (Category.METADATA, Category.STRUCTURE):
            return any(lead.category == category for lead in workspace.scan.leads)
        return True

    def _finding(self, workspace: Workspace, item: Any) -> Finding | None:
        if not isinstance(item, dict) or not item.get("title"):
            return None
        try:
            severity = Severity(str(item.get("severity", "low")).lower())
        except ValueError:
            severity = Severity.LOW
        category_name = str(item.get("category", "typography")).lower()
        category = Category(category_name if category_name in CATEGORIES else "typography")
        page_no, box, text = None, None, None
        ids = [i for i in item.get("word_ids") or [] if isinstance(i, str) and i in workspace.words]
        if ids:
            resolved = workspace.resolve(ids)
            page_no = resolved[0][1].number
            same_page = [w for _, p, w in resolved if p.number == page_no]
            box = union_box([w.box for w in same_page])
            text = " ".join(w.text for w in same_page)
        elif item.get("page") in workspace.pages and isinstance(item.get("box"), list):
            page_no = int(item["page"])
            try:
                box = workspace.pixel_box(workspace.pages[page_no], item["box"])
            except ValueError:
                box = None
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        evidence = {str(k)[:40]: (v if isinstance(v, (int, float)) else str(v)[:120]) for k, v in list(evidence.items())[:12]}
        if not self._grounded(workspace, category, ids, page_no, box) and severity in (Severity.HIGH, Severity.MEDIUM):
            severity = Severity.LOW
            evidence["grounded"] = "no"
        if category == Category.SEMANTIC and severity == Severity.HIGH:
            severity = Severity.MEDIUM
        return Finding(
            category=category,
            severity=severity,
            title=str(item["title"])[:140],
            detail=str(item.get("detail") or "")[:900],
            page=page_no,
            box=box,
            text=text,
            evidence={**evidence, "source": "agent"},
        )
