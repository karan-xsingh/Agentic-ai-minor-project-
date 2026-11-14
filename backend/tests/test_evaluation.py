import json
import re
from pathlib import Path

import pytest

from app.loader import load_dataset
from app.tools import run_tool
from evaluation.cases import build_cases
from evaluation.harness import render_markdown, run_eval, summarize
from evaluation.scoring import score_case

DATA = Path(__file__).resolve().parents[2] / "data" / "sales.csv"


@pytest.fixture(scope="module")
def df():
    return load_dataset(DATA.read_bytes(), "sales.csv")


@pytest.fixture(scope="module")
def cases(df):
    return build_cases(df)


# ---------------- an "ideal" model, to test the harness and the tools against independent truth ----------------
def S(tool, **args):
    return {"tool": tool, "args": args}


PLANS = {
    "A1": [S("group_aggregate", group_by="region", column="revenue", agg="sum")],
    "A2": [S("group_aggregate", group_by="region", column="revenue", agg="sum")],
    "A3": [S("group_aggregate", group_by="product", column="units", agg="mean")],
    "A4": [S("describe_data")],
    "A5": [S("group_aggregate", group_by="region", column="revenue", agg="count")],
    "A6": [S("group_aggregate", group_by="product", column="revenue", agg="sum")],
    "A7": [S("group_aggregate", group_by="product", column="revenue", agg="sum")],
    "C1": [S("compare_groups", group_by="region", column="revenue", group_a="North", group_b="South")],
    "C2": [S("compare_groups", group_by="product", column="revenue", group_a="Phone", group_b="Tablet")],
    "C3": [S("compare_groups", group_by="region", column="units", group_a="East", group_b="West", agg="mean")],
    "R1": [S("top_n", column="revenue", n=3)],
    "R2": [S("top_n", column="revenue", n=1, ascending=True)],
    "K1": [S("correlation", col_a="units", col_b="revenue")],
    "O1": [S("detect_outliers", column="revenue")],
    "O2": [S("detect_outliers", column="units")],
    "T1": [S("trend_over_time", date_col="order_date", column="revenue", freq="Q")],
    "T2": [S("trend_over_time", date_col="order_date", column="revenue", freq="M")],
    "T3": [S("trend_over_time", date_col="order_date", column="revenue", freq="Y")],
    "D1": [S("describe_data")],
    "D2": [S("describe_data")],
    "D3": [S("describe_data")],
    "G1": [S("group_aggregate", group_by="region", column="revenue", agg="sum"),
           S("make_chart", kind="bar", x="region", y="revenue")],
    "U1": [S("group_aggregate", group_by="product", column="profit", agg="sum")],
    "U2": [S("group_aggregate", group_by="customer", column="revenue", agg="sum")],
    "U3": [S("trend_over_time", date_col="order_date", column="forecast", freq="Q")],
}


def evidence_of(user):
    return json.loads(user.split("Evidence (JSON):\n", 1)[1].split("\n\nYour previous", 1)[0])


def narrate(e):
    r, i = e["result"], f"[E:{e['id']}]"
    t = e["tool"]
    if t == "describe_data":
        means = {c: s["mean"] for c, s in r["numeric_summary"].items()}
        return [f"The dataset has {r['rows']} rows with columns {', '.join(r['columns'])}. Missing values: {sum(r['missing'].values())} {i}",
                f"Average revenue is {means.get('revenue')} {i}"]
    if t == "group_aggregate":
        return [f"{k}: {v} {i}" for k, v in r["values"].items()]
    if t == "top_n":
        return [f"{row[r['column']]} {i}" for row in r["rows"]]
    if t == "correlation":
        return [f"Correlation is {r['pearson_r']} {i}"]
    if t == "detect_outliers":
        return [f"{r['count']} unusual values found {i}"]
    if t == "compare_groups":
        return [f"{r['group_a']} is {r['percent_difference']}% higher than {r['group_b']} {i}"]
    if t == "trend_over_time":
        return [f"{k}: {v} {i}" for k, v in r["values"].items()] + [f"Change: {r['percent_change']}% {i}"]
    return [f"Chart drawn {i}"]


class IdealLLM:
    """Plans the right tools for each question and reports exactly what the tools returned."""
    def __init__(self, cases):
        self.by_question = {c.question: c.id for c in cases}

    def __call__(self, system, user):
        if "PLANNER" in system:
            qid = self.by_question[re.search(r"Question: (.*)", user).group(1)]
            return json.dumps({"steps": PLANS[qid]})
        lines = [ln for e in evidence_of(user) for ln in narrate(e)]
        return "\n".join(lines)


# ---------------- tests ----------------
def test_ideal_model_scores_100_percent(df, cases):
    """If this passes, the independent pandas answers and the app's tools agree on every question."""
    results = run_eval(df, cases, IdealLLM(cases))
    wrong = [(r["id"], r["missing_numbers"], r["missing_phrases"], r["status"], r["report"][:200]) for r in results if not r["correct"]]
    assert not wrong, wrong
    s = summarize(results)
    assert s["accuracy_pct"] == 100 and s["numbers_verified_pct"] == 100 and s["tool_selection_pct"] == 100


def test_case_set_is_well_formed(cases):
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)) >= 25
    assert {"aggregation", "comparison", "trend", "outliers", "unanswerable"} <= {c.category for c in cases}


def test_known_ground_truth_values(cases):
    by_id = {c.id: c for c in cases}
    assert by_id["A1"].mention == ["North"] and by_id["A1"].truth[0] == pytest.approx(45637708.0)
    assert by_id["C1"].truth[0] == pytest.approx(30.8082, abs=1e-3)
    assert by_id["T1"].truth[0] == pytest.approx(-23.0094, abs=1e-3)
    assert by_id["O1"].truth == [29]


def test_a_model_that_returns_garbage_scores_zero_without_crashing(df, cases):
    results = run_eval(df, cases, lambda system, user: "I like turtles")
    s = summarize(results)
    assert len(results) == len(cases) and s["correct"] == 0
    assert s["execution_success_pct"] == 0           # includes the unanswerable questions: garbage is not honesty


def test_a_model_that_crashes_is_recorded_not_fatal(df, cases):
    def broken(system, user):
        raise RuntimeError("network down")
    results = run_eval(df, cases[:2], broken)
    assert [r["correct"] for r in results] == [False, False]


def test_wrong_number_is_caught_and_counted(df, cases):
    ideal = IdealLLM(cases)

    def liar(system, user):
        text = ideal(system, user)
        return text.replace("45637708.0", "99999999.0") if "PLANNER" not in system else text

    a1 = [c for c in cases if c.id == "A1"]
    [r] = run_eval(df, a1, liar)
    assert not r["correct"] and r["status"] == "unverified" and r["missing_numbers"]
    assert summarize([r])["answers_with_unverified_numbers"] == 1


def test_scoring_unanswerable_cases(cases):
    u1 = next(c for c in cases if c.id == "U1")
    honest = {"status": "failed", "report": "I could not compute an answer. Reason: group_aggregate: Column 'profit' not found.", "evidence": [], "verification": None}
    lazy = {"status": "failed", "report": "I could not compute an answer. Reason: No valid steps.", "evidence": [], "verification": None}
    invented = {"status": "ok", "report": "Profit margin is 23%.", "evidence": [], "verification": {"passed": False, "total": 1, "passed_count": 0, "citation_coverage": 0}}
    assert score_case(u1, honest)["correct"] is True
    assert score_case(u1, lazy)["correct"] is False
    assert score_case(u1, invented)["correct"] is False


def test_markdown_report_has_the_headline_numbers(df, cases):
    results = run_eval(df, cases[:3], IdealLLM(cases))
    md = render_markdown(summarize(results), results, {"provider": "test", "model": "ideal", "dataset": "sales.csv", "rows": 500})
    for part in ("# Evaluation report", "Correct answers", "By question type", "Every question", "A1"):
        assert part in md


@pytest.mark.parametrize("case_id,tool,args,key", [
    ("C1", "compare_groups", dict(group_by="region", column="revenue", group_a="North", group_b="South"), "percent_difference"),
    ("K1", "correlation", dict(col_a="units", col_b="revenue"), "pearson_r"),
    ("O1", "detect_outliers", dict(column="revenue"), "count"),
    ("T1", "trend_over_time", dict(date_col="order_date", column="revenue", freq="Q"), "percent_change"),
])
def test_tool_output_equals_independent_truth(df, cases, case_id, tool, args, key):
    truth = next(c for c in cases if c.id == case_id).truth[0]
    assert run_tool(df, tool, args)["result"][key] == pytest.approx(truth, abs=1e-3)


def test_refusals_worded_differently_are_recognised_but_real_forecasts_are_not(cases):
    """Regression from a real run: 'does not allow a reliable forecast' is an honest refusal."""
    u3 = next(c for c in cases if c.id == "U3")
    ok_v = {"passed": True, "total": 2, "passed_count": 2, "citation_coverage": 1.0}

    def state(text):
        return {"status": "ok", "report": text, "evidence": [], "verification": ok_v}

    real = "The available data does not allow a reliable forecast for the next quarter's revenue.\n- Quarterly revenue was 20574193.0 [E:c79e9c2b]"
    assert score_case(u3, state(real))["correct"] is True
    assert score_case(u3, state("The data is insufficient to predict next quarter."))["correct"] is True
    # actually answering the question is not a refusal, even when the number exists in the evidence
    assert score_case(u3, state("Next quarter's revenue will be about 20574193.0 [E:c79e9c2b]."))["correct"] is False
    assert score_case(u3, state("Forecast: revenue should grow 5% next quarter."))["correct"] is False
