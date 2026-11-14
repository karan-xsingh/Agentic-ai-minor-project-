// Turns the report text + the verifier's per-number results into renderable pieces.

const VERIFIED = new Set(["grounded", "grounded_uncited", "from_question"]);
export const isVerified = (status) => VERIFIED.has(status);

const CITATION = /\s*[[(][^\])]*\bE:\w+[^\])]*[\])]/g; // [E:ab12cd34] or (E:ab12cd34)
const EVIDENCE_ID = /\bE:(\w+)/g;
const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** One block per non-empty report line. */
export function parseReport(report, numbers = []) {
  return report
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const item = line.match(/^(?:[-*\u2022]|\d+[.)])\s+(.*)$/);
      const heading = line.match(/^#{1,6}\s+(.*)$/);
      const body = item ? item[1] : heading ? heading[1] : line;
      const kind = /^WARNING:/.test(line) ? "warning" : item ? "item" : heading ? "heading" : "para";
      const ids = [...new Set([...line.matchAll(EVIDENCE_ID)].map((m) => m[1]))];
      return {
        kind,
        text: body.replace(CITATION, "").trim(),
        ids,
        // The verifier stores each line as line.strip()[:140]; use the same key to find its numbers.
        numbers: numbers.filter((n) => n.line === line.slice(0, 140)),
      };
    });
}

/** Split a line into plain / bold / number pieces. Numbers carry their verification status. */
export function inlineParts(text, numbers = []) {
  const queues = new Map();
  for (const n of numbers) {
    if (!queues.has(n.number)) queues.set(n.number, []);
    queues.get(n.number).push(n);
  }
  const tokens = [...queues.keys()].sort((a, b) => b.length - a.length).map(escapeRegExp);
  const numberRe = tokens.length ? new RegExp(`(?<![\\w.])(${tokens.join("|")})(?!\\w)`, "g") : null;

  const out = [];
  const pushPlain = (chunk, bold) => {
    if (!chunk) return;
    if (!numberRe) return void out.push({ text: chunk, bold });
    chunk.split(numberRe).forEach((piece, i) => {
      if (!piece) return;
      if (i % 2 === 0) return void out.push({ text: piece, bold });
      const hit = queues.get(piece)?.shift();
      out.push(hit ? { text: piece, bold, status: hit.status, evidenceId: hit.evidence_id } : { text: piece, bold });
    });
  };

  const boldRe = /\*\*(.+?)\*\*/g;
  let last = 0;
  let m;
  while ((m = boldRe.exec(text))) {
    pushPlain(text.slice(last, m.index), false);
    pushPlain(m[1], true);
    last = m.index + m[0].length;
  }
  pushPlain(text.slice(last), false);
  return out;
}

/** Plain-language summary of the verifier result. */
export function verificationSummary(v) {
  if (!v) return null;
  if (v.total === 0) return { ok: true, text: "The answer contains no numbers to check." };
  const cited = Math.round(v.citation_coverage * 100);
  if (v.passed) {
    return {
      ok: true,
      text: `All ${v.total} ${v.total === 1 ? "number matches" : "numbers match"} the calculations. ${cited}% name their source.`,
    };
  }
  const bad = v.total - v.passed_count;
  return { ok: false, text: `${bad} of ${v.total} numbers could not be matched to a calculation.` };
}

const NUMERIC = /^(u?int|float)/;
const TEXTUAL = new Set(["object", "str", "string", "category"]);

/** Starter questions built from the dataset's own column names. */
export function suggestQuestions(columns) {
  const numeric = columns.filter((c) => NUMERIC.test(c.dtype)).map((c) => c.name);
  const text = columns.filter((c) => TEXTUAL.has(c.dtype) && !/date|time/i.test(c.name)).map((c) => c.name);
  const date = columns.find((c) => /date|time/i.test(c.name))?.name;
  const out = ["Give me an overview of this dataset"];
  if (text[0] && numeric.at(-1)) out.push(`Which ${text[0]} has the highest total ${numeric.at(-1)}?`);
  if (numeric.at(-1)) out.push(`Are there unusual ${numeric.at(-1)} values?`);
  if (date && numeric.at(-1)) out.push(`Show the quarterly ${numeric.at(-1)} trend`);
  if (numeric.length >= 2) out.push(`Are ${numeric[0]} and ${numeric.at(-1)} correlated?`);
  return out.slice(0, 5);
}

export const describeArgs = (args) =>
  Object.entries(args ?? {})
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");

const PROBLEM_TEXT = {
  ungrounded: "does not appear in any calculation.",
  misattributed: "exists in the results, but not in the step it points to.",
  invalid_citation: "points to a step that does not exist.",
};

/** One plain sentence per number that failed verification. */
export function problemLines(v) {
  const seen = new Set();
  return (v?.numbers ?? [])
    .filter((n) => !isVerified(n.status))
    .map((n) => `${n.number} ${PROBLEM_TEXT[n.status] ?? "could not be checked."}`)
    .filter((line) => !seen.has(line) && seen.add(line));
}

/** Display-only: 45637708.0 becomes 45,637,708. Small numbers (years, counts) are left alone. */
export function formatNumber(text) {
  if (/^-?\d{1,3}(,\d{3})+\.0+$/.test(text)) return text.replace(/\.0+$/, ""); // 45,637,708.0 -> 45,637,708
  if (!/^-?\d+(\.\d+)?$/.test(text)) return text;
  const n = Number(text);
  if (Math.abs(n) < 10000) return text;
  return Number.isInteger(n) ? n.toLocaleString("en-US") : n.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

/** Compact formatting for overview statistics. */
export function formatStat(n) {
  if (n === null || n === undefined) return "n/a";
  return Number.isInteger(n) ? n.toLocaleString("en-US") : n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

/** Four plain-language stages describing what the agent did for one answer. */
export function runSummary(a) {
  const calcs = (a.evidence ?? []).slice(1); // evidence[0] is the automatic dataset profile, not a planned step
  const okCalcs = calcs.filter((e) => e.ok).length;
  const failedCalcs = calcs.length - okCalcs;
  const answered = a.status === "ok" || a.status === "unverified";
  const v = a.verification;

  return [
    {
      key: "plan",
      title: "Planned",
      detail: a.attempts > 1 ? `Needed ${a.attempts} tries to get a valid plan` : "Chose the analysis on the first try",
      tone: calcs.length === 0 ? "bad" : a.attempts > 1 ? "warn" : "ok",
    },
    {
      key: "calculate",
      title: "Calculated",
      detail: calcs.length === 0
        ? "No calculation ran"
        : `${okCalcs} ${okCalcs === 1 ? "calculation" : "calculations"} succeeded${failedCalcs ? `, ${failedCalcs} failed` : ""}`,
      tone: calcs.length === 0 || okCalcs === 0 ? "bad" : failedCalcs ? "warn" : "ok",
    },
    {
      key: "write",
      title: "Wrote the answer",
      detail: !answered ? "No answer could be written" : a.report_attempts > 1 ? `Rewrote it ${a.report_attempts - 1} time${a.report_attempts > 2 ? "s" : ""}` : "First draft was kept",
      tone: !answered ? "bad" : a.report_attempts > 1 ? "warn" : "ok",
    },
    {
      key: "check",
      title: "Checked the numbers",
      detail: !v ? "Skipped, nothing to check" : v.total === 0 ? "The answer has no numbers" : `${v.passed_count} of ${v.total} matched a calculation`,
      tone: !v ? "bad" : v.passed ? "ok" : "bad",
    },
  ];
}
