"""Run the full analysis on a folder of labelled documents and report accuracy.

Usage (inside the api container):
    python -m scripts.evaluate /samples            # uses /samples/labels.json
labels.json maps file name -> "edited" | "genuine".
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

from app.agent import Investigator
from app.config import get_settings
from app.forensics import analyze_file
from app.llm import ChatClient


def main(folder: Path) -> int:
    labels = json.loads((folder / "labels.json").read_text())
    settings = get_settings()
    client = ChatClient(settings)
    investigator = Investigator(client, settings.agent_max_steps, settings.agent_max_images) if client.enabled else None
    print(f"mode: {'agent (' + client.model + ')' if investigator else 'rules only'}\n")
    correct = 0
    for name, truth in labels.items():
        start = time.perf_counter()
        result = analyze_file((folder / name).read_bytes(), Path(tempfile.mkdtemp()), settings.ocr_lang, investigator)
        flagged = result["label"] != "likely_authentic"
        ok = flagged == (truth == "edited")
        correct += ok
        inv = result.get("investigation") or {}
        print(f"{'PASS' if ok else 'FAIL'} {name}: truth={truth} label={result['label']} risk={result['risk_score']:.2f} "
              f"steps={len(inv.get('steps', []))} {time.perf_counter() - start:.0f}s {('ERROR ' + inv['error']) if 'error' in inv else ''}")
        print(f"     summary: {result['summary']}")
        for f in result["findings"][:5]:
            print(f"     [{f['severity']}] {f['title']} | {f['text']!r} | {f['detail'][:160]}")
        if inv.get("steps"):
            print("     trail: " + " > ".join(f"{s['tool']}({s['input']})" for s in inv["steps"])[:600])
        print()
    print(f"accuracy: {correct}/{len(labels)}")
    return 0 if correct == len(labels) else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "/samples")))
