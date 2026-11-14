"""Run the evaluation against your real LLM.

    python -m evaluation.run                 # all questions
    python -m evaluation.run --delay 4       # wait 4 s between questions (free-tier rate limits)
    python -m evaluation.run --ids A1,C1     # only some questions
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from app.llm import LLMError, make_llm
from app.loader import load_dataset

from .cases import build_cases
from .harness import render_markdown, run_eval, summarize

DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "sales.csv"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the data-analysis agent.")
    ap.add_argument("--data", default=str(DEFAULT_DATA), help="CSV used for the evaluation")
    ap.add_argument("--ids", default="", help="comma-separated question ids, e.g. A1,C1")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds to wait between questions")
    args = ap.parse_args(argv)

    try:
        llm = make_llm()
    except LLMError as exc:
        print(f"LLM is not set up: {exc}")
        return 1

    path = Path(args.data)
    df = load_dataset(path.read_bytes(), path.name)
    cases = build_cases(df)
    if args.ids:
        wanted = {i.strip().upper() for i in args.ids.split(",")}
        cases = [c for c in cases if c.id in wanted]
        if not cases:
            print("No question matches those ids.")
            return 1

    def progress(i, n, r):
        print(f"[{i:>2}/{n}] {r['id']:<3} {'correct' if r['correct'] else 'WRONG  '}  {r['seconds']:>5.1f}s  {r['question'][:60]}", flush=True)

    print(f"Running {len(cases)} questions with {os.getenv('LLM_PROVIDER')} / {os.getenv('LLM_MODEL')} ...")
    results = run_eval(df, cases, llm, delay=args.delay, progress=progress)
    summary = summarize(results)
    meta = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "provider": os.getenv("LLM_PROVIDER"),
            "model": os.getenv("LLM_MODEL"), "dataset": path.name, "rows": len(df)}

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    (RESULTS_DIR / f"eval-{stamp}.json").write_text(json.dumps({"meta": meta, "summary": summary, "results": results}, indent=2), encoding="utf-8")
    report_path = RESULTS_DIR / f"eval-{stamp}.md"
    markdown = render_markdown(summary, results, meta)
    report_path.write_text(markdown, encoding="utf-8")
    (RESULTS_DIR / "latest.md").write_text(markdown, encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"Correct answers          : {summary['correct']} of {summary['cases']} ({summary['accuracy_pct']}%)")
    print(f"Unanswerable handled     : {summary['unanswerable_handled_pct']}%")
    print(f"Right tool chosen        : {summary['tool_selection_pct']}%")
    print(f"Numbers verified         : {summary['numbers_verified_pct']}% of {summary['numbers_checked']}")
    print(f"Median / slowest 5% time : {summary['latency_median_s']} s / {summary['latency_p95_s']} s")
    print(f"Full report              : {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
