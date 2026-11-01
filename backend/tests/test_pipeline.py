from app.forensics import analyze_file
from app.agent import Investigation
from app.forensics.types import Category, Finding, Severity
from tests.synth import BODY, render, scan, to_bytes, words

EDITED = [
    words(BODY[0], "serif", 34),
    words("The below mentioned student wish to join as", "serif", 34) + words("Research Intern in", "sans", 32),
    words(BODY[2], "serif", 34),
    words(BODY[3], "serif", 34),
]


def test_clean_scan_is_likely_authentic(tmp_out):
    raw = to_bytes(scan(render([words(l, "serif", 34) for l in BODY])), "JPEG")
    result = analyze_file(raw, tmp_out)
    assert result["label"] == "likely_authentic", result["findings"]
    assert result["document"]["kind"] == "image" and result["document"]["page_count"] == 1
    page = result["pages"][0]
    assert (tmp_out / page["image"]).is_file()
    assert (tmp_out / page["layers"]["ela"]).is_file() and (tmp_out / page["layers"]["noise"]).is_file()
    assert "Typography consistency" in result["checks_passed"]
    assert result["ocr"][0]["lines"] and result["summary_source"] == "rules"


def test_edited_scan_is_flagged_with_box(tmp_out):
    result = analyze_file(to_bytes(scan(render(EDITED))), tmp_out)
    assert result["label"] != "likely_authentic"
    top = result["findings"][0]
    assert top["severity"] in ("high", "medium") and top["page"] == 1
    assert all(0 <= v <= 1 for v in top["box"])
    assert "Research" in (top["text"] or "") or "Intern" in (top["text"] or "")


class FakeInvestigator:
    def __init__(self, fail: bool = False):
        self.fail, self.scan = fail, None

    def run(self, scan):
        self.scan = scan
        if self.fail:
            raise RuntimeError("model unavailable")
        page = scan.document.pages[0]
        word = next(w for w in page.words if "Research" in w.text)
        finding = Finding(Category.TYPOGRAPHY, Severity.HIGH, "Inserted phrase", "sans in serif line",
                          page=1, box=word.box, text=word.text, evidence={"source": "agent"})
        return Investigation(verdict="highly_risky", summary="One phrase was typed in later.", findings=[finding],
                             steps=[{"tool": "compare", "input": "3 vs 8 peers", "ok": True}], model="fake")


def test_investigator_result_replaces_heuristic_findings(tmp_out):
    investigator = FakeInvestigator()
    result = analyze_file(to_bytes(scan(render(EDITED))), tmp_out, investigator=investigator)
    assert investigator.scan.leads is not None and investigator.scan.document.pages[0].words
    assert result["summary_source"] == "agent" and result["summary"] == "One phrase was typed in later."
    assert result["investigation"]["model"] == "fake" and result["investigation"]["steps"][0]["tool"] == "compare"
    assert [f["title"] for f in result["findings"]] == ["Inserted phrase"]
    assert result["label"] != "likely_authentic"


def test_investigator_failure_falls_back_to_rules(tmp_out):
    result = analyze_file(to_bytes(scan(render(EDITED))), tmp_out, investigator=FakeInvestigator(fail=True))
    assert result["summary_source"] == "rules" and "model unavailable" in result["investigation"]["error"]
    assert result["findings"]