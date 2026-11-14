"""Runs the cases, summarises the results and writes a Markdown report."""
from __future__ import annotations
import statistics
import time
from datetime import datetime

import pandas as pd

from app.agent import run_agent

from .cases import Case
from .scoring import score_case


def run_eval(df: pd.DataFrame, cases: list[Case], llm, delay: float = 0.0, progress=None) -> list[dict]:
    results = []
    for i, case in enumerate(cases, 1):
        started = time.perf_counter()
        try:
            state = run_agent(df, case.question, llm)
            error = None
        except Exception as exc:                      # a crash is a result, not a reason to stop
            state, error = {"status": "crashed", "report": f"CRASH: {exc}"}, str(exc)
        seconds = time.perf_counter() - started
        result = score_case(case, state)
        result.update(seconds=round(seconds, 2), error=error)
        results.append(result)
        if progress:
            progress(i, len(cases), result)
        if delay and i < len(cases):
            time.sleep(delay)                         # stay under the provider's rate limit
    return results


def _pct(n: int, d: int) -> float | None:
    return None if d == 0 else round(100 * n / d, 1)


def summarize(results: list[dict]) -> dict:
    answerable = [r for r in results if not r["refusal"]]
    refusals = [r for r in results if r["refusal"]]
    scored_tools = [r for r in results if r["tool_ok"] is not None]
    answered = [r for r in answerable if r["answered"]]
    times = sorted(r["seconds"] for r in results)
    total_nums = sum(r["numbers_total"] for r in results)

    by_category = {}
    for r in results:
        c = by_category.setdefault(r["category"], {"cases": 0, "correct": 0})
        c["cases"] += 1
        c["correct"] += r["correct"]
    for c in by_category.values():
        c["accuracy_pct"] = _pct(c["correct"], c["cases"])

    return {
        "cases": len(results),
        "correct": sum(r["correct"] for r in results),
        "accuracy_pct": _pct(sum(r["correct"] for r in results), len(results)),
        "answerable_accuracy_pct": _pct(sum(r["correct"] for r in answerable), len(answerable)),
        "unanswerable_handled_pct": _pct(sum(r["correct"] for r in refusals), len(refusals)),
        "tool_selection_pct": _pct(sum(bool(r["tool_ok"]) for r in scored_tools), len(scored_tools)),
        "execution_success_pct": _pct(len(answered), len(answerable)),
        "numbers_checked": total_nums,
        "numbers_verified_pct": _pct(sum(r["numbers_verified"] for r in results), total_nums),
        "fully_verified_answers_pct": _pct(sum(r["status"] == "ok" for r in answered), len(answered)),
        "answers_with_unverified_numbers": sum(r["status"] == "unverified" for r in results),
        "retried_runs_pct": _pct(sum(r["attempts"] > 1 or r["report_attempts"] > 1 for r in results), len(results)),
        "latency_mean_s": round(statistics.mean(times), 2) if times else None,
        "latency_median_s": round(statistics.median(times), 2) if times else None,
        "latency_p95_s": round(times[min(len(times) - 1, int(0.95 * len(times)))], 2) if times else None,
        "by_category": by_category,
    }


def render_markdown(summary: dict, results: list[dict], meta: dict) -> str:
    s = summary
    fmt = lambda x, suffix="": "n/a" if x is None else f"{x}{suffix}"
    yn = lambda b: "n/a" if b is None else ("Yes" if b else "No")
    lines = [
        "# Evaluation report", "",
        f"- **Date:** {meta.get('date', datetime.now().strftime('%Y-%m-%d %H:%M'))}",
        f"- **Model:** {meta.get('provider', '?')} / {meta.get('model', '?')}",
        f"- **Dataset:** {meta.get('dataset', '?')} ({meta.get('rows', '?')} rows)",
        f"- **Questions:** {s['cases']}, with correct answers computed independently using pandas", "",
        "## Headline results", "",
        "| Measure | Result |", "|---|---|",
        f"| Correct answers (all questions) | {s['correct']} of {s['cases']} ({fmt(s['accuracy_pct'], '%')}) |",
        f"| Correct answers (answerable questions) | {fmt(s['answerable_accuracy_pct'], '%')} |",
        f"| Unanswerable questions handled honestly | {fmt(s['unanswerable_handled_pct'], '%')} |",
        f"| Right analysis tool chosen | {fmt(s['tool_selection_pct'], '%')} |",
        f"| Answers produced without failure | {fmt(s['execution_success_pct'], '%')} |",
        f"| Numbers in answers matched to a calculation | {fmt(s['numbers_verified_pct'], '%')} of {s['numbers_checked']} |",
        f"| Answers where every number verified | {fmt(s['fully_verified_answers_pct'], '%')} |",
        f"| Answers still carrying unverified numbers | {s['answers_with_unverified_numbers']} |",
        f"| Runs that needed a retry or rewrite | {fmt(s['retried_runs_pct'], '%')} |",
        f"| Response time (mean / median / slowest 5%) | {fmt(s['latency_mean_s'])} s / {fmt(s['latency_median_s'])} s / {fmt(s['latency_p95_s'])} s |",
        "", "## By question type", "", "| Type | Questions | Correct | Accuracy |", "|---|---|---|---|",
    ]
    for name, c in s["by_category"].items():
        lines.append(f"| {name} | {c['cases']} | {c['correct']} | {fmt(c['accuracy_pct'], '%')} |")
    lines += ["", "## Every question", "", "| ID | Question | Correct | Right tool | Numbers verified | Time |", "|---|---|---|---|---|---|"]
    for r in results:
        nums = f"{r['numbers_verified']}/{r['numbers_total']}" if r["numbers_total"] else "none"
        lines.append(f"| {r['id']} | {r['question']} | {yn(r['correct'])} | {yn(r['tool_ok'])} | {nums} | {r['seconds']} s |")
    wrong = [r for r in results if not r["correct"]]
    lines += ["", "## What went wrong", ""]
    if not wrong:
        lines.append("Every question was answered correctly.")
    for r in wrong:
        why = []
        if r["status"] not in ("ok", "unverified") and not r["refusal"]:
            why.append(f"no answer (status {r['status']})")
        if r["missing_numbers"]:
            why.append("missing numbers " + ", ".join(f"{x:,.4g}" for x in r["missing_numbers"]))
        if r["missing_phrases"]:
            why.append("missing words " + ", ".join(r["missing_phrases"]))
        if r["tool_ok"] is False:
            why.append("tools used: " + (", ".join(r["tools_run"]) or "none"))
        lines += [f"**{r['id']}** {r['question']}", f"- {'; '.join(why) or 'did not meet the expected behaviour'}",
                  f"- Answer given: {r['report'][:300].replace(chr(10), ' ')}", ""]
    return "\n".join(lines) + "\n"
