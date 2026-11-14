import { runSummary } from "../lib/report.js";
import { Alert, Check, Cross } from "./Icons.jsx";

const ICON = { ok: Check, warn: Alert, bad: Cross };

export default function RunTrace({ analysis }) {
  return (
    <section className="trace" aria-labelledby="trace-title">
      <h3 id="trace-title" className="section__title">How the agent worked</h3>
      <ol className="trace__steps">
        {runSummary(analysis).map((s) => {
          const Icon = ICON[s.tone];
          return (
            <li key={s.key} className={`trace__step trace__step--${s.tone}`}>
              <span className="trace__dot"><Icon width={16} height={16} /></span>
              <p className="trace__title">{s.title}</p>
              <p className="trace__detail">{s.detail}</p>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
