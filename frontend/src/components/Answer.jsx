import { reportUrl } from "../api.js";
import { problemLines, verificationSummary } from "../lib/report.js";
import Chart from "./Chart.jsx";
import EvidenceList from "./EvidenceList.jsx";
import ReportView from "./ReportView.jsx";
import RunTrace from "./RunTrace.jsx";

const STATUS = {
  ok: { label: "Verified", tone: "ok" },
  unverified: { label: "Needs review", tone: "warn" },
  failed: { label: "No answer", tone: "bad" },
  llm_error: { label: "No answer", tone: "bad" },
};

export default function Answer({ analysis, activeEvidence, onSelectEvidence, theme }) {
  const status = STATUS[analysis.status] ?? { label: analysis.status, tone: "warn" };
  const summary = verificationSummary(analysis.verification);
  const hasNumbers = (analysis.verification?.total ?? 0) > 0;

  return (
    <article className="answer" aria-label="Answer">
      <header className="answer__head">
        <div>
          <p className="answer__question">{analysis.question}</p>
          <p className="answer__meta">Took {(analysis.duration_ms / 1000).toFixed(1)} seconds</p>
        </div>
        <div className="answer__actions">
          <span className={`badge badge--${status.tone}`}>{status.label}</span>
          <a className="btn" href={reportUrl(analysis.analysis_id)} download>Download report</a>
        </div>
      </header>

      <ReportView report={analysis.report} verification={analysis.verification} onSelect={onSelectEvidence} />

      {summary && (
        <p className={`verdict ${summary.ok ? "verdict--ok" : "verdict--bad"}`}>
          {summary.text}
          {hasNumbers && summary.ok && " Select a highlighted number to see how it was calculated."}
        </p>
      )}
      {analysis.verification && !analysis.verification.passed && (
        <ul className="problems">
          {problemLines(analysis.verification).map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}

      {analysis.charts.length > 0 && (
        <section aria-label="Charts" className="charts">
          {analysis.charts.map((c) => <Chart key={c.evidence_id} chart={c} theme={theme} />)}
        </section>
      )}

      <RunTrace analysis={analysis} />
      <EvidenceList evidence={analysis.evidence} active={activeEvidence} />
    </article>
  );
}
