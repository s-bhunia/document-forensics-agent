import json

import pytest

from app.agent import Investigator
from app.agent.tools import TOOLS, dispatch
from app.agent.workspace import Scan, Workspace
from app.forensics.ocr import extract_words
from app.forensics.textfeatures import measure_page
from app.forensics.types import Category, Document, Finding, Page, Severity
from tests.synth import render, scan, words

LINES = [
    words("NAME DIPAK SHAW KUMAR", "dejavu-bold", 36),
    words("FATHER RABINDRA SHAW SINGH", "dejavu-bold", 36),
    words("ISSUED 24-01-2007 RENEWED 09-03-2011", "dejavu-bold", 36),
    words("BIRTH", "dejavu-bold", 36) + words("04/11/2005", "dejavu", 36) + words("VALID 23-01-2027", "dejavu-bold", 36),
]


@pytest.fixture(scope="module")
def workspace() -> Workspace:
    img = scan(render(LINES))
    page = Page(number=1, image=img, words=extract_words(img))
    measure_page(page)
    lead = Finding(Category.STRUCTURE, Severity.MEDIUM, "PDF was changed after it was first saved", "2 revisions")
    return Workspace(Scan(document=Document(kind="image", pages=[page], metadata={"format": "PNG"}), leads=[lead]))


def _id(ws: Workspace, text: str) -> str:
    return next(wid for wid, (_, w) in ws.words.items() if w.text == text)


def test_overview_lists_word_ids_and_leads(workspace):
    text = workspace.overview()
    assert "p1w1" in text and "RABINDRA" in text and "L1 [medium/structure]" in text


def test_measure_and_compare_flag_regular_among_bold(workspace):
    dob = _id(workspace, "04/11/2005")
    peers = [_id(workspace, t) for t in ("DIPAK", "RABINDRA", "KUMAR", "SINGH")]
    assert "04/11/2005" in workspace.measure([dob]).text
    table = workspace.compare([dob], peers).text
    assert "stroke_px" in table and "YES" in table
    assert dob in workspace.measured and all(p in workspace.measured for p in peers)


def test_digit_widths_find_peers_and_images(workspace):
    widths = workspace.digit_widths(1).text
    assert "24-01-2007" in widths and "dd-dd-dddd" in widths
    peers = workspace.find_peers(_id(workspace, "24-01-2007")).text
    assert "same number format" in peers and "23-01-2027" in peers
    zoom = workspace.zoom(1, [0.0, 0.5, 0.6, 0.5])
    assert zoom.images and zoom.images[0][1].startswith("data:image/jpeg;base64,")
    assert "region" in workspace.region_forensics(1, [0.1, 0.1, 0.5, 0.3]).text
    assert workspace.regions


def test_dispatch_errors_are_explicit(workspace):
    with pytest.raises(ValueError):
        dispatch(workspace, "measure", {"word_ids": ["p9w9"]})
    with pytest.raises(ValueError):
        dispatch(workspace, "nope", {})
    with pytest.raises(ValueError):
        workspace.zoom(1, [0.5, 0.5, 0.0001, 0.0001])
    assert {t["function"]["name"] for t in TOOLS} >= {"measure", "compare", "zoom", "submit_report"}


class ScriptedChat:
    model = "scripted"

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, messages, tools=None, tool_choice=None):
        self.calls.append({"messages": list(messages), "tools": [t["function"]["name"] for t in tools or []]})
        step = self.script.pop(0)
        return step(messages) if callable(step) else step


def _call(name, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)},
            "extra_content": {"google": {"thought_signature": "sig"}}}


def _scan(workspace):
    return workspace.scan


def test_investigator_runs_tools_and_grounds_findings(workspace):
    dob = _id(workspace, "04/11/2005")
    peers = [_id(workspace, t) for t in ("DIPAK", "RABINDRA", "KUMAR")]
    unmeasured = _id(workspace, "SINGH")
    report = {
        "verdict": "highly_risky",
        "summary": "The DOB was retyped.",
        "findings": [
            {"title": "DOB in regular weight", "detail": "lighter", "severity": "high", "category": "typography",
             "word_ids": [dob], "evidence": {"stroke_px": 3.1}},
            {"title": "Unmeasured claim", "detail": "x", "severity": "high", "category": "typography", "word_ids": [unmeasured]},
            {"title": "Invented structure", "detail": "x", "severity": "high", "category": "copy_move", "page": 1, "box": [0.1, 0.1, 0.2, 0.2]},
            {"title": "Sum mismatch", "detail": "x", "severity": "high", "category": "semantic"},
        ],
    }
    chat = ScriptedChat([
        {"role": "assistant", "content": None, "tool_calls": [_call("compare", {"target_ids": [dob], "peer_ids": peers}, "a"),
                                                             _call("zoom", {"page": 1, "box": [0, 0.6, 0.5, 0.4]}, "b")]},
        {"role": "assistant", "content": None, "tool_calls": [_call("submit_report", report, "c")]},
    ])
    result = Investigator(chat, max_steps=5).run(_scan(workspace))
    by_title = {f.title: f for f in result.findings}
    assert result.verdict == "highly_risky" and result.model == "scripted"
    assert by_title["DOB in regular weight"].severity == Severity.HIGH and by_title["DOB in regular weight"].box
    assert by_title["Unmeasured claim"].severity == Severity.LOW
    assert by_title["Invented structure"].severity == Severity.LOW
    assert by_title["Sum mismatch"].severity == Severity.MEDIUM
    second = chat.calls[1]["messages"]
    assert second[2]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "sig"
    assert [m["role"] for m in second[3:6]] == ["tool", "tool", "user"]
    assert any(part.get("type") == "image_url" for part in second[5]["content"])
    assert [s["tool"] for s in result.steps] == ["compare", "zoom", "submit_report"]


def test_tool_errors_are_returned_to_the_model(workspace):
    chat = ScriptedChat([
        {"role": "assistant", "tool_calls": [_call("measure", {"word_ids": ["p7w1"]})]},
        {"role": "assistant", "tool_calls": [_call("submit_report", {"verdict": "likely_authentic", "summary": "ok", "findings": []}, "d")]},
    ])
    result = Investigator(chat).run(_scan(workspace))
    assert "Error: unknown word id" in chat.calls[1]["messages"][-1]["content"]
    assert result.steps[0]["ok"] is False and result.findings == []


def test_budget_forces_report(workspace):
    looping = {"role": "assistant", "tool_calls": [_call("read_text", {"page": 1})]}
    finish = {"role": "assistant", "tool_calls": [_call("submit_report", {"verdict": "bogus", "summary": "", "findings": []})]}
    chat = ScriptedChat([looping, looping, finish])
    result = Investigator(chat, max_steps=2).run(_scan(workspace))
    assert chat.calls[-1]["tools"] == ["submit_report"] and result.verdict == "suspicious"


def test_no_report_raises(workspace):
    chat = ScriptedChat([{"role": "assistant", "content": "thinking"}] * 3)
    with pytest.raises(RuntimeError):
        Investigator(chat, max_steps=5).run(_scan(workspace))
