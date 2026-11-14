import { Calc, Chat, Plan, Shield } from "./Icons.jsx";

const STEPS = [
  { icon: Chat, title: "You ask", text: "Write your question in plain English." },
  { icon: Plan, title: "The agent plans", text: "It picks from a fixed set of safe analysis tools. It never writes free-form code." },
  { icon: Calc, title: "Code calculates", text: "Python computes every number directly from your data." },
  { icon: Shield, title: "Numbers are checked", text: "Each number in the answer must match a calculation, or it is flagged." },
];

export default function Welcome({ onSample, busy }) {
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <h2 id="welcome-title" className="welcome__title">Answers you can check, not just trust</h2>
      <p className="welcome__lede">
        Upload a spreadsheet and ask about it in plain English. You get a written answer, charts, and the calculations
        behind every number.
      </p>
      <div className="welcome__actions">
        <button type="button" className="btn btn--primary" onClick={onSample} disabled={busy}>
          {busy ? "Loading…" : "Try the sample sales data"}
        </button>
        <span className="welcome__or">or add your own file on the left</span>
      </div>

      <ol className="flow" aria-label="How it works">
        {STEPS.map(({ icon: Icon, title, text }) => (
          <li key={title} className="flow__step">
            <span className="flow__icon"><Icon /></span>
            <h3 className="flow__title">{title}</h3>
            <p className="flow__text">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
