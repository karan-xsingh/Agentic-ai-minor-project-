import { Fragment } from "react";
import { formatNumber, inlineParts, isVerified, parseReport } from "../lib/report.js";

function Piece({ part, onSelect }) {
  if (!part.status) return part.bold ? <strong>{part.text}</strong> : part.text;
  const shown = formatNumber(part.text);
  const content = part.bold ? <strong>{shown}</strong> : shown;
  if (isVerified(part.status)) {
    return part.evidenceId ? (
      <button type="button" className="num num--ok" onClick={() => onSelect(part.evidenceId)} title={`Show how ${part.text} was calculated`}>
        {content}
      </button>
    ) : (
      <span className="num num--ok" title="Matches a calculation">{content}</span>
    );
  }
  return <span className="num num--bad" title="Could not be matched to any calculation">{content}</span>;
}

function Line({ block, onSelect }) {
  return (
    <>
      {inlineParts(block.text, block.numbers).map((part, i) => (
        <Fragment key={i}><Piece part={part} onSelect={onSelect} /></Fragment>
      ))}
      {block.ids.map((id) => (
        <button key={id} type="button" className="ref" onClick={() => onSelect(id)} title="Show this calculation">
          {id}
        </button>
      ))}
    </>
  );
}

export default function ReportView({ report, verification, onSelect }) {
  const blocks = parseReport(report, verification?.numbers ?? []);
  const nodes = [];
  let items = [];
  const flush = () => {
    if (items.length) nodes.push(<ul key={`ul${nodes.length}`} className="report__list">{items}</ul>);
    items = [];
  };
  blocks.forEach((b, i) => {
    if (b.kind === "item") {
      items.push(<li key={i}><Line block={b} onSelect={onSelect} /></li>);
      return;
    }
    flush();
    if (b.kind === "heading") nodes.push(<h3 key={i} className="report__heading">{b.text}</h3>);
    else if (b.kind === "warning") return; // the verdict below already says this
    else nodes.push(<p key={i} className={`report__para ${nodes.length === 0 ? "report__lead" : ""}`}><Line block={b} onSelect={onSelect} /></p>);
  });
  flush();
  return <div className="report">{nodes}</div>;
}
