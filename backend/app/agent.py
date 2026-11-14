r"""LangGraph workflow (Step 2):

    profile -> plan -> execute --(tool errors & retries left)--> plan
                          \--(otherwise)--> report -> verify --(bad numbers, 1 retry)--> report
                                                          \--(otherwise)--> END

The LLM only chooses WHICH whitelisted tools to run and with WHAT arguments.
All numbers come from run_tool(); the report must cite evidence IDs.
"""
from __future__ import annotations
import inspect
import json
import re
from typing import TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from .llm import LLM
from .tools import TOOLS, run_tool
from .verify import verify_report

MAX_STEPS = 4      # tool calls per plan
MAX_RETRIES = 2    # re-plans after tool errors
CHART_WORDS = re.compile(r"\b(chart|plot|graph|visuali[sz]\w*|histogram|diagram)\b", re.I)
MAX_REPORT_RETRIES = 1   # re-writes after failed number verification


class AgentState(TypedDict, total=False):
    question: str
    plan: list[dict]
    evidence: list[dict]
    charts: list[dict]
    feedback: str
    attempts: int
    report: str
    status: str
    report_attempts: int
    plan_note: str
    report_feedback: str
    verification: dict | None


# ---------- prompt helpers ----------
def tool_catalog() -> str:
    lines = []
    for name, fn in TOOLS.items():
        params = ", ".join(str(p) for n, p in inspect.signature(fn).parameters.items() if n != "df")
        lines.append(f"- {name}({params}): {(fn.__doc__ or '').strip()}")
    return "\n".join(lines)


def parse_plan(text: str) -> list[dict]:
    """Extract {"steps":[...]} from LLM text; keep only whitelisted tools."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    data = None
    for candidate in (cleaned, (re.search(r"\{.*\}", cleaned, re.S) or [None])[0]):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    if isinstance(data, dict) and "steps" not in data and "arguments" in data:   # pseudo tool-call wrapper
        data = data["arguments"]
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = None
    steps = data.get("steps", []) if isinstance(data, dict) else []
    out = []
    for s in steps:
        if isinstance(s, dict) and s.get("tool") in TOOLS and isinstance(s.get("args", {}), dict):
            out.append({"tool": s["tool"], "args": s.get("args", {})})
    return out[:MAX_STEPS]


def compact_evidence(evidence: list[dict]) -> list[dict]:
    """What the LLM sees: successful results only; chart JSON stripped (too big)."""
    out = []
    for e in evidence:
        if not e["ok"]:
            continue
        result = e["result"]
        if e["tool"] == "make_chart":
            result = {k: v for k, v in result.items() if k != "figure"}
        out.append({"id": e["id"], "tool": e["tool"], "args": e["args"], "result": result})
    return out


PLAN_SYSTEM = (
    "You are a data-analysis PLANNER. Choose which tools to run to answer the question.\n"
    'Respond with JSON only, no prose: {"steps":[{"tool":"<name>","args":{...}}]}\n'
    "Do NOT use function-calling syntax; write the JSON as plain text.\n"
    "Guidance:\n"
    "- average -> agg mean; total -> agg sum; how many -> agg count.\n"
    "- highest/lowest/most/least per category -> group_aggregate with the right agg.\n"
    "- X vs Y, how much higher/lower -> compare_groups.\n"
    "- change or trend over time -> trend_over_time (freq Q or M).\n"
    "- unusual or outlier values -> detect_outliers.\n"
    "- dataset overview, column names, missing values, or an overall average/min/max -> describe_data.\n"
    "- Use make_chart only if the user asks for a chart/plot/graph, and always together with an analysis tool.\n"
    f"Use at most {MAX_STEPS} steps. Use exact column names. Available tools:\n@@CATALOG@@"
)

REPORT_SYSTEM = (
    "You are a careful data analyst writing a short report.\n"
    "Rules: use ONLY numbers present in the evidence; never compute or guess new numbers; "
    "write numbers exactly as in the evidence (rounding is fine) and keep their sign: write -43.58, "
    "never an en dash or the word minus; if the evidence lists partial_periods, say those are incomplete; "
    "end EVERY line that contains a number with an evidence id like [E:ab12cd34], including the first line; if the evidence cannot answer "
    "the question, say so. Structure: a one-line answer, then 2-5 bullet findings."
)


# ---------- graph ----------
def build_agent(df: pd.DataFrame, llm: LLM):
    def profile(state: AgentState) -> AgentState:
        return {"evidence": [run_tool(df, "describe_data", {})], "charts": [],
                "attempts": 0, "feedback": "", "report_attempts": 0,
                "report_feedback": "", "verification": None}

    def plan(state: AgentState) -> AgentState:
        attempts = state.get("attempts", 0) + 1
        sample = df.head(3).to_dict("records")
        user = (f"Columns and types: { {c: str(t) for c, t in df.dtypes.items()} }\n"
                f"Sample rows: {json.dumps(sample, default=str)}\n"
                f"Question: {state['question']}\n")
        if state.get("feedback"):
            user += f"\nYour previous plan had problems, fix them: {state['feedback']}\n"
        try:
            steps = parse_plan(llm(PLAN_SYSTEM.replace("@@CATALOG@@", tool_catalog()), user))
        except Exception as exc:  # LLMError, network, etc.
            return {"plan": [], "attempts": attempts, "status": "llm_error",
                    "feedback": f"LLM call failed: {exc}"}
        note = ""
        if steps and all(x["tool"] == "make_chart" for x in steps) and not CHART_WORDS.search(state["question"]):
            steps = []
            note = ("A chart alone does not answer the question; also run an analysis tool "
                    "(group_aggregate, compare_groups, trend_over_time, ...).")
        return {"plan": steps, "attempts": attempts, "status": "", "plan_note": note}

    def execute(state: AgentState) -> AgentState:
        if state.get("status") == "llm_error":      # keep the real error message
            return {}
        evidence, charts, problems = list(state["evidence"]), list(state["charts"]), []
        if not state["plan"]:
            problems.append(state.get("plan_note") or "No valid steps. Return JSON with whitelisted tools only.")
        for step in state["plan"]:
            rec = run_tool(df, step["tool"], step["args"])
            evidence.append(rec)
            if not rec["ok"]:
                problems.append(f"{step['tool']}: {rec['error']}")
            elif step["tool"] == "make_chart":
                charts.append({"evidence_id": rec["id"], **rec["result"]})
        return {"evidence": evidence, "charts": charts, "feedback": "; ".join(problems)}

    def route(state: AgentState) -> str:
        if state.get("status") == "llm_error":
            return "report"
        return "plan" if state["feedback"] and state["attempts"] <= MAX_RETRIES else "report"

    def report(state: AgentState) -> AgentState:
        planned = state["evidence"][1:]          # evidence[0] is the automatic dataset profile, not a planned step
        usable = compact_evidence(planned)
        if not usable:
            why = state.get("feedback") or "no analysis steps succeeded"
            return {"report": f"I could not compute an answer. Reason: {why}",
                    "status": state.get("status") or "failed"}
        user = (f"Question: {state['question']}\n\n"
                f"Evidence (JSON):\n{json.dumps(compact_evidence(state['evidence']), default=str)}")
        if state.get("feedback"):
            user += (f"\n\nThese analysis steps failed and produced no results: {state['feedback']}\n"
                     "Say clearly what could not be computed and why. Do not guess it.")
        if state.get("report_feedback"):
            user += ("\n\nYour previous draft contained numbers that could not be verified against "
                     f"the evidence: {state['report_feedback']}\nRewrite the report using ONLY numbers "
                     "that appear in the evidence (rounding is fine). Do not calculate new numbers "
                     "(no sums, differences, percentages or averages).")
        n = state.get("report_attempts", 0) + 1
        try:
            text = llm(REPORT_SYSTEM, user)
        except Exception as exc:
            return {"report": f"Analysis ran but the report step failed: {exc}",
                    "status": "llm_error", "report_attempts": n}
        return {"report": text.strip(), "status": "ok", "report_attempts": n}

    def verify(state: AgentState) -> AgentState:
        if state.get("status") != "ok":
            return {"verification": None}
        v = verify_report(state["report"], state["evidence"], state["question"])
        if v["passed"]:
            return {"verification": v, "report_feedback": ""}
        if state["report_attempts"] <= MAX_REPORT_RETRIES:
            return {"verification": v, "report_feedback": "; ".join(v["problems"])}
        bad = ", ".join(r["number"] for r in v["numbers"] if r["status"] not in ("grounded", "grounded_uncited", "from_question"))
        return {"verification": v, "status": "unverified",
                "report": state["report"] + f"\n\nWARNING: these numbers could not be verified against the computed evidence: {bad}"}

    def route_verify(state: AgentState) -> str:
        v = state.get("verification")
        if v and not v["passed"] and state.get("status") == "ok":
            return "report"
        return END

    g = StateGraph(AgentState)
    g.add_node("profile", profile)
    g.add_node("plan", plan)
    g.add_node("execute", execute)
    g.add_node("report", report)
    g.add_node("verify", verify)
    g.add_edge(START, "profile")
    g.add_edge("profile", "plan")
    g.add_edge("plan", "execute")
    g.add_conditional_edges("execute", route, {"plan": "plan", "report": "report"})
    g.add_edge("report", "verify")
    g.add_conditional_edges("verify", route_verify, {"report": "report", END: END})
    return g.compile()


def run_agent(df: pd.DataFrame, question: str, llm: LLM) -> AgentState:
    return build_agent(df, llm).invoke({"question": question})
