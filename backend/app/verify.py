r"""Verification layer (Step 3).

Checks every number in the LLM's report against the evidence produced by the tools.
No LLM is involved here: this is plain, testable code.

Per-number statuses
  grounded          number found in the evidence the line cites           (pass)
  grounded_uncited  number found in some evidence, but the line has no [E:id]  (pass, lowers citation coverage)
  from_question     number was given by the user in the question           (pass)
  misattributed     number exists, but not in the evidence that was cited  (FAIL)
  invalid_citation  line cites an evidence id that does not exist          (FAIL)
  ungrounded        number appears nowhere in the evidence (invented/computed by the LLM)  (FAIL)
"""
from __future__ import annotations
import re

MULT = {"k": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9,
        "lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7}

NUM_RE = re.compile(
    r"(?<![\w.])([-\u2212\u2013]?\d[\d,]*(?:\.\d+)?)(?:\s?(%|million|billion|lakhs?|crores?|bn|k|m|b))?(?![\w])",
    re.I)
CITE_BRACKET = re.compile(r"\[[^\]]*\bE:[^\]]*\]")
CITE_ID = re.compile(r"\bE:(\w+)")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
LIST_MARK = re.compile(r"^\s*(?:\d+[.)]|[-*\u2022])\s+")

PASSING = {"grounded", "grounded_uncited", "from_question"}


def extract_numbers(text: str) -> list[dict]:
    """Find numbers like 45,637,708.0 | 45.6 million | 12 lakh | 35% | -0.36."""
    text = DATE_RE.sub(" ", text)
    out = []
    for m in NUM_RE.finditer(text):
        base = m.group(1).rstrip(",")
        suffix = (m.group(2) or "").lower()
        try:
            val = float(base.replace(",", "").replace("\u2212", "-").replace("\u2013", "-"))
        except ValueError:
            continue
        percent = suffix == "%"
        mult = 1.0 if (percent or not suffix) else MULT[suffix]
        decimals = len(base.split(".")[1]) if "." in base else 0
        out.append({"raw": m.group(0).strip().rstrip(","), "value": val * mult,
                    "decimals": decimals, "mult": mult, "percent": percent})
    return out


def collect_numbers(obj) -> list[float]:
    """Every number inside an evidence record (values, numeric keys, numeric strings)."""
    if obj is None or isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)] if obj == obj else []   # skip NaN
    if isinstance(obj, str):
        return [n["value"] for n in extract_numbers(obj)]
    if isinstance(obj, dict):
        return [x for k, v in obj.items() for x in collect_numbers(k) + collect_numbers(v)]
    if isinstance(obj, (list, tuple)):
        return [x for v in obj for x in collect_numbers(v)]
    return []


def _matches(n: dict, candidates) -> bool:
    """Rounding-aware match: '45.6 million' matches 45,637,708; '36%' matches 0.36."""
    tol = 0.5 * 10 ** (-n["decimals"]) * n["mult"]
    for c in candidates:
        if abs(n["value"] - c) <= tol + 1e-9 * max(1.0, abs(c)):
            return True
        if n["percent"] and abs(n["value"] - c * 100) <= tol + 1e-9 * max(1.0, abs(c * 100)):
            return True
    return False


def verify_report(report: str, evidence: list[dict], question: str = "") -> dict:
    by_id = {e["id"]: collect_numbers(e["args"]) + collect_numbers(e["result"])
             for e in evidence if e["ok"]}
    question_vals = [n["value"] for n in extract_numbers(question)]
    all_vals = [v for vals in by_id.values() for v in vals]

    results = []
    for line in report.splitlines():
        ids = CITE_ID.findall(line)
        clean = LIST_MARK.sub("", CITE_BRACKET.sub("", line))
        for n in extract_numbers(clean):
            matched_id, status = None, "ungrounded"
            if ids and any(i not in by_id for i in ids):
                status = "invalid_citation"
            elif ids:
                hit = next((i for i in ids if _matches(n, by_id[i])), None)
                if hit:
                    status, matched_id = "grounded", hit
                elif _matches(n, all_vals):
                    status = "misattributed"
                elif _matches(n, question_vals):
                    status = "from_question"
            else:
                if _matches(n, all_vals):
                    status = "grounded_uncited"
                elif _matches(n, question_vals):
                    status = "from_question"
            results.append({"number": n["raw"], "status": status, "evidence_id": matched_id,
                            "line": line.strip()[:140], "cited": bool(ids)})

    failed = [r for r in results if r["status"] not in PASSING]
    total = len(results)
    return {
        "numbers": results,
        "total": total,
        "passed_count": total - len(failed),
        "score": (total - len(failed)) / total if total else 1.0,
        "citation_coverage": (sum(r["cited"] for r in results) / total) if total else 1.0,
        "passed": not failed,
        "problems": [f"'{r['number']}' is {r['status']} in: {r['line']}" for r in failed],
    }
