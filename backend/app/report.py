"""Downloadable Markdown report (Step 4)."""
from __future__ import annotations
import json


def _cell(text: str, limit: int = 160) -> str:
    text = str(text).replace("|", "\\|").replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def build_markdown(analysis: dict, dataset: dict) -> str:
    v = analysis.get("verification")
    lines = [
        "# Data analysis report", "",
        f"- **Dataset:** {dataset['filename']} ({dataset['rows']} rows)",
        f"- **Question:** {analysis['question']}",
        f"- **Status:** {analysis['status']}",
        f"- **Generated:** {analysis['created_at']}  (took {analysis['duration_ms']} ms)", "",
        "## Answer", "", analysis["report"], "",
        "## Verification", "",
    ]
    if v:
        lines.append(f"{v['passed_count']} of {v['total']} numbers verified against computed evidence "
                     f"({v['score']:.0%}); citation coverage {v['citation_coverage']:.0%}.")
        lines += [f"- PROBLEM: {p}" for p in v["problems"]]
    else:
        lines.append("No numbers were verified (analysis did not complete).")
    lines += ["", "## Evidence trail", "", "| ID | Tool | Arguments | Result |", "|---|---|---|---|"]
    for e in analysis["evidence"]:
        result = e["result"] if e["ok"] else f"ERROR: {e['error']}"
        lines.append(f"| {e['id']} | {e['tool']} | {_cell(json.dumps(e['args']))} | "
                     f"{_cell(json.dumps(result, default=str))} |")
    return "\n".join(lines) + "\n"
