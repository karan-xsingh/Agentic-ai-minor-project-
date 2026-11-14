"""Scores one agent run against its evaluation case."""
from __future__ import annotations
import re

from app.verify import CITE_BRACKET, _matches, extract_numbers

from .cases import Case

REFUSAL_WORDS = ("cannot", "can't", "couldn't", "could not", "not found", "not available", "does not contain",
                 "doesn't contain", "unable", "not possible", "no column", "no data", "do not have",
                 "don't have", "no such", "not provide", "not include", "isn't", "not supported", "no information",
                 "does not allow", "do not allow", "not enough", "insufficient", "does not support", "does not include",
                 "does not provide", "not able to", "cannot be", "can not", "not reliable", "unreliable", "lacks", "lack of")
GENERIC_FAILURE = "I could not compute an answer."


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("_", " "))


def _numbers_in(report: str) -> list[dict]:
    return extract_numbers(CITE_BRACKET.sub("", report))


def score_case(case: Case, state: dict) -> dict:
    report = state.get("report", "") or ""
    status = state.get("status", "")
    v = state.get("verification")
    ran_ok = {e["tool"] for e in state.get("evidence", []) if e["ok"]}
    answered = status in ("ok", "unverified")

    # --- tool selection (not scored when the always-run describe_data step is the expected tool) ---
    expected = set(case.tools_any) | set(case.tools_all)
    if not expected or "describe_data" in case.tools_any:
        tool_ok = None
    else:
        tool_ok = (not case.tools_any or bool(set(case.tools_any) & ran_ok)) and set(case.tools_all) <= ran_ok

    # --- correctness ---
    missing_truth, missing_mentions = [], []
    if case.refusal:
        text = report.replace(GENERIC_FAILURE, "").lower()
        no_invented = v is None or v.get("passed") or v.get("total", 0) == 0
        said_no = any(w in text for w in REFUSAL_WORDS)
        correct = bool(no_invented and said_no and status != "llm_error")
    else:
        nums = _numbers_in(report)
        missing_truth = [t for t in case.truth if not any(_matches(n, [t]) for n in nums)]
        norm = _norm(report)
        missing_mentions = [m for m in case.mention if _norm(m) not in norm]
        any_ok = not case.mention_any or any(_norm(m) in norm for m in case.mention_any)
        chart_ok = not case.needs_chart or len(state.get("charts", [])) >= 1
        correct = answered and not missing_truth and not missing_mentions and any_ok and chart_ok

    return {
        "id": case.id, "category": case.category, "question": case.question, "refusal": case.refusal,
        "status": status, "correct": correct, "tool_ok": tool_ok, "answered": answered,
        "missing_numbers": missing_truth, "missing_phrases": missing_mentions,
        "numbers_total": v["total"] if v else 0, "numbers_verified": v["passed_count"] if v else 0,
        "citation_coverage": v["citation_coverage"] if v else None,
        "attempts": state.get("attempts", 0), "report_attempts": state.get("report_attempts", 0),
        "tools_run": sorted(ran_ok - {"describe_data"}),
        "report": report[:700],
    }
