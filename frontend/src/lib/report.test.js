import { describe, expect, test } from "vitest";
import { describeArgs, inlineParts, parseReport, problemLines, suggestQuestions, verificationSummary } from "./report.js";

const num = (number, status, evidence_id, line) => ({ number, status, evidence_id, line });

describe("parseReport", () => {
  test("strips list markers and both citation styles, keeps ids", () => {
    const blocks = parseReport("North leads [E:aaaa1111].\n- South: 5 (E:bbbb2222).\n* East [E:cccc3333, E:dddd4444]");
    expect(blocks.map((b) => b.kind)).toEqual(["para", "item", "item"]);
    expect(blocks[0].text).toBe("North leads.");
    expect(blocks[1].text).toBe("South: 5.");
    expect(blocks[1].ids).toEqual(["bbbb2222"]);
    expect(blocks[2].ids).toEqual(["cccc3333", "dddd4444"]);
  });

  test("recognises the warning line and headings", () => {
    const kinds = parseReport("# Result\nWARNING: these numbers could not be verified: 5").map((b) => b.kind);
    expect(kinds).toEqual(["heading", "warning"]);
  });

  test("attaches verifier numbers to the matching line", () => {
    const line = "- North: 300 [E:aaaa1111]";
    const [block] = parseReport(line, [num("300", "grounded", "aaaa1111", line), num("9", "ungrounded", null, "other line")]);
    expect(block.numbers).toHaveLength(1);
  });
});

describe("inlineParts", () => {
  test("marks verified and failed numbers", () => {
    const parts = inlineParts("North 300 beat South 999", [
      num("300", "grounded", "aaaa1111"),
      num("999", "ungrounded", null),
    ]);
    const stamped = parts.filter((p) => p.status);
    expect(stamped.map((p) => [p.text, p.status])).toEqual([["300", "grounded"], ["999", "ungrounded"]]);
    expect(stamped[0].evidenceId).toBe("aaaa1111");
  });

  test("the same number twice consumes results in order", () => {
    const parts = inlineParts("5 and 5", [num("5", "grounded", "e1"), num("5", "ungrounded", null)]);
    expect(parts.filter((p) => p.status).map((p) => p.status)).toEqual(["grounded", "ungrounded"]);
  });

  test("handles bold text and thousands separators", () => {
    const parts = inlineParts("**Watch** sold 45,637,708.0 units", [num("45,637,708.0", "grounded", "e1")]);
    expect(parts[0]).toMatchObject({ text: "Watch", bold: true });
    expect(parts.find((p) => p.status).text).toBe("45,637,708.0");
  });

  test("does not match a number inside a longer one", () => {
    const parts = inlineParts("2300 and 300", [num("300", "grounded", "e1")]);
    expect(parts.filter((p) => p.status)).toHaveLength(1);
    expect(parts.find((p) => p.status).text).toBe("300");
  });

  test("works with no numbers", () => {
    expect(inlineParts("plain text", [])).toEqual([{ text: "plain text", bold: false }]);
  });
});

describe("helpers", () => {
  test("verificationSummary wording", () => {
    expect(verificationSummary(null)).toBeNull();
    expect(verificationSummary({ total: 6, passed_count: 6, passed: true, citation_coverage: 0.83 }).text).toContain("All 6 numbers match");
    const bad = verificationSummary({ total: 6, passed_count: 4, passed: false, citation_coverage: 1 });
    expect(bad.ok).toBe(false);
    expect(bad.text).toBe("2 of 6 numbers could not be matched to a calculation.");
  });

  test("suggestQuestions uses real column names", () => {
    const cols = [
      { name: "order_date", dtype: "str" }, { name: "region", dtype: "str" },
      { name: "units", dtype: "int64" }, { name: "revenue", dtype: "float64" },
    ];
    const qs = suggestQuestions(cols);
    expect(qs).toContain("Which region has the highest total revenue?");
    expect(qs).toContain("Show the quarterly revenue trend");
    expect(qs).toContain("Are units and revenue correlated?");
  });

  test("describeArgs", () => {
    expect(describeArgs({ group_by: "region", n: 3 })).toBe("group_by=region, n=3");
  });
});

test("problemLines explains each failure once, in plain words", () => {
  const v = { numbers: [
    num("99,999", "ungrounded", null), num("99,999", "ungrounded", null),
    num("5", "misattributed", null), num("7", "invalid_citation", null), num("300", "grounded", "e1"),
  ] };
  expect(problemLines(v)).toEqual([
    "99,999 does not appear in any calculation.",
    "5 exists in the results, but not in the step it points to.",
    "7 points to a step that does not exist.",
  ]);
  expect(problemLines(null)).toEqual([]);
});

import { formatNumber, formatStat, runSummary } from "./report.js";

describe("display formatting", () => {
  test("formatNumber groups big numbers and leaves small ones, years and text alone", () => {
    expect(formatNumber("45637708.0")).toBe("45,637,708");
    expect(formatNumber("-11646751.0")).toBe("-11,646,751");
    expect(formatNumber("12345.6789")).toBe("12,345.6789");
    expect(formatNumber("2025")).toBe("2025");
    expect(formatNumber("10.3182")).toBe("10.3182");
    expect(formatNumber("45.6 million")).toBe("45.6 million");
    expect(formatNumber("1,234,567")).toBe("1,234,567");
    expect(formatNumber("45,637,708.0")).toBe("45,637,708");
    expect(formatNumber("1,234.50")).toBe("1,234.50");
  });
  test("formatStat", () => {
    expect(formatStat(2500000)).toBe("2,500,000");
    expect(formatStat(9.71623)).toBe("9.72");
    expect(formatStat(null)).toBe("n/a");
  });
});

describe("runSummary", () => {
  const ev = (tool, ok = true) => ({ tool, ok });
  const base = { status: "ok", attempts: 1, report_attempts: 1, verification: { total: 9, passed_count: 9, passed: true },
    evidence: [ev("describe_data"), ev("group_aggregate"), ev("top_n")] };

  test("clean run", () => {
    const s = runSummary(base);
    expect(s.map((x) => x.tone)).toEqual(["ok", "ok", "ok", "ok"]);
    expect(s[1].detail).toBe("2 calculations succeeded");
    expect(s[3].detail).toBe("9 of 9 matched a calculation");
  });
  test("retries and a failed calculation are shown as warnings", () => {
    const s = runSummary({ ...base, attempts: 2, report_attempts: 2, evidence: [ev("describe_data"), ev("top_n", false), ev("group_aggregate")] });
    expect(s.map((x) => x.tone)).toEqual(["warn", "warn", "warn", "ok"]);
    expect(s[1].detail).toBe("1 calculation succeeded, 1 failed");
    expect(s[2].detail).toBe("Rewrote it 1 time");
  });
  test("unverified numbers fail the last stage", () => {
    const s = runSummary({ ...base, status: "unverified", verification: { total: 3, passed_count: 2, passed: false } });
    expect(s[3]).toMatchObject({ tone: "bad", detail: "2 of 3 matched a calculation" });
  });
  test("no answer at all", () => {
    const s = runSummary({ status: "failed", attempts: 3, report_attempts: 0, verification: null, evidence: [ev("describe_data")] });
    expect(s.map((x) => x.tone)).toEqual(["bad", "bad", "bad", "bad"]);
  });
});

test("a describe_data step the planner chose counts as a calculation (overview questions)", () => {
  const s = runSummary({ status: "ok", attempts: 1, report_attempts: 1, verification: { total: 2, passed_count: 2, passed: true },
    evidence: [{ tool: "describe_data", ok: true }, { tool: "describe_data", ok: true }] });
  expect(s.map((x) => x.tone)).toEqual(["ok", "ok", "ok", "ok"]);
  expect(s[1].detail).toBe("1 calculation succeeded");
});
