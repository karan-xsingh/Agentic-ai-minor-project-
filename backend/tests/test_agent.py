import json
import re
import pandas as pd
import pytest
from app.agent import parse_plan, run_agent


@pytest.fixture
def df():
    return pd.DataFrame({"region": ["N", "N", "S", "S"], "sales": [100, 200, 50, 150]})


def scripted(plans, calls=None):
    """Fake LLM: returns each plan in turn; the report cites the first real evidence id."""
    plans = list(plans)

    def llm(system, user):
        if calls is not None:
            calls.append((system[:20], user))
        if "PLANNER" in system:
            return plans.pop(0) if plans else '{"steps":[]}'
        ids = re.findall(r'"id": "(\w{8})"', user)
        return f"North leads with 300 total [E:{ids[-1]}]"
    return llm


GOOD = json.dumps({"steps": [{"tool": "group_aggregate",
                              "args": {"group_by": "region", "column": "sales", "agg": "sum"}}]})
BAD_COL = json.dumps({"steps": [{"tool": "group_aggregate",
                                 "args": {"group_by": "area", "column": "sales"}}]})


def test_happy_path(df):
    s = run_agent(df, "total sales by region?", scripted([GOOD]))
    assert s["status"] == "ok" and s["attempts"] == 1
    cited = re.findall(r"\[E:(\w{8})\]", s["report"])
    assert cited and cited[0] in {e["id"] for e in s["evidence"]}


def test_retry_after_tool_error(df):
    calls = []
    s = run_agent(df, "q", scripted([BAD_COL, GOOD], calls))
    assert s["status"] == "ok" and s["attempts"] == 2
    second_plan_prompt = [u for sysm, u in calls if sysm.startswith("You are a data-analy")][1]
    assert "not found" in second_plan_prompt          # error fed back to the planner


def test_gives_up_after_max_retries(df):
    s = run_agent(df, "q", scripted([BAD_COL, BAD_COL, BAD_COL]))
    assert s["status"] == "failed" and s["attempts"] == 3
    assert "could not compute" in s["report"]


def test_unknown_tool_is_filtered():
    plan = json.dumps({"steps": [{"tool": "os_system", "args": {"cmd": "dir"}}]})
    assert parse_plan(plan) == []


def test_garbage_llm_output_is_safe(df):
    s = run_agent(df, "q", scripted(["sorry I can't do JSON", "nope", "still nope"]))
    assert s["status"] == "failed"


def test_markdown_fenced_json_is_accepted():
    assert len(parse_plan("```json\n" + GOOD + "\n```")) == 1


def test_llm_outage_is_handled(df):
    def broken(system, user):
        raise RuntimeError("network down")
    s = run_agent(df, "q", broken)
    assert s["status"] == "llm_error" and "could not compute" in s["report"]


def test_chart_is_collected(df):
    plan = json.dumps({"steps": [{"tool": "make_chart", "args": {"kind": "bar", "x": "region", "y": "sales"}}]})
    s = run_agent(df, "chart it", scripted([plan]))
    assert len(s["charts"]) == 1 and s["charts"][0]["kind"] == "bar"


def test_llm_error_message_is_preserved(df):
    def broken(system, user):
        raise RuntimeError("API key not valid")
    s = run_agent(df, "q", broken)
    assert "API key not valid" in s["report"]


def test_pseudo_tool_call_wrapper_is_unwrapped():
    wrapped = json.dumps({"name": "commentary", "arguments": json.loads(GOOD)})
    assert len(parse_plan(wrapped)) == 1


def test_chart_only_plan_is_rejected_and_replanned(df):
    chart_only = json.dumps({"steps": [{"tool": "make_chart", "args": {"kind": "bar", "x": "region", "y": "sales"}}]})
    calls = []
    s = run_agent(df, "which region has the most sales?", scripted([chart_only, GOOD], calls))
    assert s["attempts"] == 2 and s["status"] == "ok" and s["charts"] == []
    assert "chart alone" in [u for _, u in calls if "Question" in u][1]


DESCRIBE_ONLY = json.dumps({"steps": [{"tool": "describe_data", "args": {}}]})


def test_question_answered_by_the_dataset_summary_alone(df):
    """Regression: overview/missing-value/column questions only need describe_data."""
    def llm(system, user):
        if "PLANNER" in system:
            return DESCRIBE_ONLY
        ids = re.findall(r'"id": "(\w{8})"', user)
        return f"The dataset has 4 rows [E:{ids[0]}]"

    s = run_agent(df, "give me an overview", llm)
    assert s["status"] == "ok" and s["verification"]["passed"] and "could not compute" not in s["report"]


def test_failed_steps_are_reported_honestly_not_hidden(df):
    bad = json.dumps({"steps": [{"tool": "describe_data", "args": {}},
                                {"tool": "group_aggregate", "args": {"group_by": "area", "column": "sales"}}]})
    seen = []

    def llm(system, user):
        if "PLANNER" in system:
            return bad
        seen.append(user)
        return "I cannot compute that: the column was not found."

    s = run_agent(df, "sales by area?", llm)
    assert s["attempts"] == 3                                   # it retried before giving up
    assert "These analysis steps failed" in seen[0] and "not found" in seen[0]
    assert s["status"] in ("ok", "unverified")
