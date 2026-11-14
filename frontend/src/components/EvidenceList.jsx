import { useEffect, useRef, useState } from "react";
import { describeArgs } from "../lib/report.js";

function Row({ e, active, tick }) {
  const [open, setOpen] = useState(false);
  const row = useRef(null);

  useEffect(() => {
    if (!active) return;
    setOpen(true);
    row.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
  }, [active, tick]);

  const body = e.ok ? JSON.stringify(e.result, null, 2) : e.error;
  const shown = body && body.length > 4000 ? `${body.slice(0, 4000)}\n…` : body;

  return (
    <li ref={row} className={`step ${active ? "step--active" : ""} ${e.ok ? "" : "step--failed"}`}>
      <button type="button" className="step__head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="step__id">{e.id}</span>
        <span className="step__call">
          <span className="step__tool">{e.tool}</span>
          <span className="step__args">{describeArgs(e.args)}</span>
        </span>
        <span className="step__state">{e.ok ? `${e.ms} ms` : "Failed"}</span>
      </button>
      {open && <pre className="step__body">{shown}</pre>}
    </li>
  );
}

export default function EvidenceList({ evidence, active }) {
  return (
    <section className="evidence" aria-labelledby="evidence-heading">
      <h3 id="evidence-heading" className="section__title">How this was calculated</h3>
      <p className="section__lede">
        Each step ran as code on your data. The answer may only use numbers these steps produced.
      </p>
      <ol className="steps">
        {evidence.map((e) => <Row key={e.id} e={e} active={e.id === active?.id} tick={active?.tick} />)}
      </ol>
    </section>
  );
}
