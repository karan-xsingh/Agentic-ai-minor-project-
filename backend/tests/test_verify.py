import json
import re
import pandas as pd
import pytest
from app.agent import run_agent
from app.verify import extract_numbers, verify_report


def ev(id_, result, args=None):
    return {"id": id_, "tool": "t", "args": args or {}, "ok": True, "result": result, "error": None, "ms": 1}


EVIDENCE = [
    ev("aaaaaaaa", {"values": {"North": 45637708.0, "South": 34889018.0}}),
    ev("bbbbbbbb", {"pearson_r": 0.3567, "n": 500}),
]


# ---------- number extraction ----------
def test_extract_formats():
    vals = {n["raw"]: n["value"] for n in extract_numbers("a 45,637,708.0, b 45.6 million, c 12 lakh, d -0.36")}
    assert vals["45,637,708.0"] == 45637708.0
    assert vals["45.6 million"] == 45.6e6
    assert vals["12 lakh"] == 12e5
    assert vals["-0.36"] == -0.36


def test_extract_ignores_dates_ordinals_and_ids():
    assert extract_numbers("on 2025-01-31 the 3rd region") == []
    report = "North leads [E:ab12cd34]"
    assert verify_report(report, EVIDENCE)["total"] == 0


# ---------- verification ----------
def test_exact_and_rounded_numbers_pass():
    r = verify_report("North: 45,637,708.0 [E:aaaaaaaa]\nAbout 45.6 million [E:aaaaaaaa]\nr = 0.36 [E:bbbbbbbb]", EVIDENCE)
    assert r["passed"] and r["total"] == 3 and r["score"] == 1.0


def test_percent_matches_fraction():
    assert verify_report("r is 35.67% [E:bbbbbbbb]", EVIDENCE)["passed"]


def test_invented_number_fails():
    r = verify_report("North leads with 50,000,000 [E:aaaaaaaa]", EVIDENCE)
    assert not r["passed"] and r["numbers"][0]["status"] == "ungrounded"


def test_llm_computed_number_fails():
    # 45,637,708 - 34,889,018 = 10,748,690 was never produced by a tool
    r = verify_report("North beats South by 10,748,690 [E:aaaaaaaa]", EVIDENCE)
    assert not r["passed"]


def test_misattributed_citation_fails():
    r = verify_report("Correlation is 45,637,708 [E:bbbbbbbb]", EVIDENCE)
    assert r["numbers"][0]["status"] == "misattributed"


def test_invalid_citation_fails():
    r = verify_report("North is 45,637,708 [E:zzzzzzzz]", EVIDENCE)
    assert r["numbers"][0]["status"] == "invalid_citation"


def test_uncited_but_real_number_passes_with_lower_coverage():
    r = verify_report("North has 45,637,708\nSouth 34,889,018 [E:aaaaaaaa]", EVIDENCE)
    assert r["passed"] and r["citation_coverage"] == 0.5


def test_number_from_question_allowed():
    r = verify_report("Here are the top 3 regions.", EVIDENCE, question="show top 3 regions")
    assert r["passed"]


def test_score_is_fraction_grounded():
    r = verify_report("North 45,637,708 [E:aaaaaaaa]\nMade up 123 [E:aaaaaaaa]", EVIDENCE)
    assert r["total"] == 2 and r["passed_count"] == 1 and r["score"] == 0.5


# ---------- graph integration ----------
@pytest.fixture
def df():
    return pd.DataFrame({"region": ["N", "N", "S", "S"], "sales": [100, 200, 50, 150]})


PLAN = json.dumps({"steps": [{"tool": "group_aggregate",
                              "args": {"group_by": "region", "column": "sales", "agg": "sum"}}]})


def make_llm(first_report, second_report):
    reports = [first_report, second_report]

    def llm(system, user):
        if "PLANNER" in system:
            return PLAN
        gid = re.findall(r'"id": "(\w{8})"', user)[-1]
        text = reports.pop(0) if len(reports) > 1 else reports[0]
        return text.replace("ID", gid)
    return llm


def test_agent_rewrites_after_hallucinated_number(df):
    llm = make_llm("N total is 999 [E:ID]", "N total is 300 [E:ID]")
    s = run_agent(df, "total by region?", llm)
    assert s["status"] == "ok" and s["report_attempts"] == 2
    assert s["verification"]["passed"] and "300" in s["report"]


def test_agent_flags_if_still_unverified(df):
    llm = make_llm("N total is 999 [E:ID]", "N total is 999 [E:ID]")
    s = run_agent(df, "total by region?", llm)
    assert s["status"] == "unverified" and "WARNING" in s["report"] and s["report_attempts"] == 2


def test_agent_verification_clean_on_first_try(df):
    s = run_agent(df, "total by region?", make_llm("N total is 300 [E:ID]", "x"))
    assert s["report_attempts"] == 1 and s["verification"]["score"] == 1.0


NEG = [ev("cccccccc", {"change": -11646751.0, "percent_change": -43.5832})]


def test_en_dash_and_unicode_minus_are_negative_signs():
    r = verify_report("Change: \u201311,646,751.0 and \u221243.58% [E:cccccccc]", NEG)
    assert r["passed"] and r["total"] == 2


def test_en_dash_ranges_are_not_negative():
    nums = extract_numbers("between 2025\u20132026 and 10\u201320 units")
    assert [n["value"] for n in nums] == [2025, 2026, 10, 20]


def test_sign_flip_is_caught():
    # evidence says -43.58; a report that says +43.58 changes the meaning and must fail
    assert not verify_report("Revenue changed by 43.58% [E:cccccccc]", NEG)["passed"]


def test_overview_counts_are_grounded_in_the_dataset_summary():
    """Regression: '5 columns' used to be flagged because the summary never contained the number 5."""
    from app.tools import run_tool
    import pandas as pd
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    e = run_tool(df, "describe_data", {})
    r = verify_report(f"The dataset has 3 rows and 2 columns [E:{e['id']}].", [e])
    assert r["passed"] and r["total"] == 2
