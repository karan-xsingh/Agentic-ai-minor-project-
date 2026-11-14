import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";
import Answer from "./Answer.jsx";
import AskBar from "./AskBar.jsx";
import Overview from "./Overview.jsx";
import RunTrace from "./RunTrace.jsx";
import UploadPanel from "./UploadPanel.jsx";
import Welcome from "./Welcome.jsx";

const line1 = "- North revenue: 45,637,708.0 [E:aaaa1111]";
const line2 = "- West revenue: 19,500,000 [E:aaaa1111]";

const analysis = {
  analysis_id: "an1", dataset_id: "ds1", question: "Which region has the highest revenue?",
  status: "unverified", duration_ms: 4200, attempts: 1, report_attempts: 2, created_at: "2026-11-07T10:00:00+00:00",
  report: `${line1}\n${line2}\nWARNING: these numbers could not be verified against the computed evidence: 19,500,000`,
  verification: {
    total: 2, passed_count: 1, passed: false, score: 0.5, citation_coverage: 1,
    problems: ["'19,500,000' is ungrounded in: West"],
    numbers: [
      { number: "45,637,708.0", status: "grounded", evidence_id: "aaaa1111", line: line1, cited: true },
      { number: "19,500,000", status: "ungrounded", evidence_id: null, line: line2, cited: true },
    ],
  },
  evidence: [
    { id: "aaaa1111", tool: "group_aggregate", args: { group_by: "region", column: "revenue" }, ok: true, result: { values: { North: 45637708 } }, error: null, ms: 3 },
    { id: "bbbb2222", tool: "top_n", args: { column: "nope" }, ok: false, result: null, error: "Column 'nope' not found", ms: 1 },
  ],
  charts: [],
};

describe("Answer", () => {
  const html = renderToStaticMarkup(<Answer analysis={analysis} activeEvidence={null} onSelectEvidence={() => {}} />);

  test("checked numbers are highlighted and the unmatched one is flagged", () => {
    expect(html).toContain('class="num num--ok"');
    expect(html).toContain('class="num num--bad"');
    expect(html).toContain(">45,637,708</button>");       // shown without the trailing .0
    expect(html).toContain("Show how 45,637,708.0 was calculated"); // hover text keeps the original
  });

  test("shows status, verdict, download link and the calculation steps", () => {
    expect(html).toContain("Needs review");
    expect(html).toContain("1 of 2 numbers could not be matched to a calculation.");
    expect(html).toContain("/analyses/an1/report.md");
    expect(html).toContain("group_aggregate");
    expect(html).toContain("group_by=region, column=revenue");
    expect(html).toContain("Failed");
  });

  test("the backend warning is not repeated, problems are plain, citations become reference buttons", () => {
    expect(html).not.toContain("WARNING:");
    expect(html).not.toContain("could not be verified against");
    expect(html).toContain("19,500,000 does not appear in any calculation.");
    expect(html).toContain('class="ref"');
    expect(html).not.toContain("[E:aaaa1111]");
  });
});

describe("other components", () => {
  test("AskBar disables Ask until there is a question and lists suggestions", () => {
    const html = renderToStaticMarkup(<AskBar question="" setQuestion={() => {}} onAsk={() => {}} busy={false} suggestions={["Give me an overview"]} />);
    expect(html).toMatch(/<button class="btn btn--primary" type="submit" disabled/);
    expect(html).toContain("Give me an overview");
  });

  test("UploadPanel shows the file summary after upload and surfaces errors", () => {
    const ds = { dataset_id: "d", filename: "sales.csv", rows: 500, columns: [{ name: "region", dtype: "str" }], preview: [{ region: "North" }], created_at: "" };
    const html = renderToStaticMarkup(<UploadPanel dataset={ds} uploading={false} error="Unsupported file type" onUpload={() => {}} />);
    expect(html).toContain("sales.csv");
    expect(html).toContain("500 rows by 1 columns");
    expect(html).toContain("Unsupported file type");
  });

  test("UploadPanel shows the public-demo notice only when given one", () => {
    const withNotice = renderToStaticMarkup(<UploadPanel dataset={null} uploading={false} error="" onUpload={() => {}} notice="Public demo: do not upload private data." />);
    const without = renderToStaticMarkup(<UploadPanel dataset={null} uploading={false} error="" onUpload={() => {}} />);
    expect(withNotice).toContain("Public demo");
    expect(without).not.toContain("Public demo");
  });
});


describe("new screens", () => {
  test("Welcome explains the pipeline and offers the sample data", () => {
    const html = renderToStaticMarkup(<Welcome onSample={() => {}} busy={false} />);
    expect(html).toContain("Try the sample sales data");
    for (const t of ["You ask", "The agent plans", "Code calculates", "Numbers are checked"]) expect(html).toContain(t);
  });

  test("RunTrace shows the four stages", () => {
    const html = renderToStaticMarkup(<RunTrace analysis={analysis} />);
    for (const t of ["Planned", "Calculated", "Wrote the answer", "Checked the numbers"]) expect(html).toContain(t);
    expect(html).toContain("1 of 2 matched a calculation");
  });

  test("Overview renders KPIs, a histogram, top values and a date range", () => {
    const profile = {
      rows: 500, columns: 3, numeric_columns: 1, missing_total: 0,
      profile: [
        { name: "units", kind: "number", missing: 0, unique: 19, min: 1, max: 19, mean: 9.716, median: 10, hist: { counts: [3, 9, 4], edges: [1, 7, 13, 19] } },
        { name: "region", kind: "category", missing: 2, unique: 4, top: [{ value: "North", count: 170 }, { value: "East", count: 120 }] },
        { name: "order_date", kind: "date", missing: 0, unique: 500, min: "2025-01-01", max: "2026-05-15", span_days: 499 },
      ],
    };
    const html = renderToStaticMarkup(<Overview profile={profile} open />);
    expect(html).toContain("None");                       // no missing values
    expect(html).toContain("<svg");                       // histogram
    expect(html).toContain("North");
    expect(html).toContain("2 missing");
    expect(html).toContain("2026-05-15");
    expect(renderToStaticMarkup(<Overview profile={null} open />)).toBe("");
  });
});
