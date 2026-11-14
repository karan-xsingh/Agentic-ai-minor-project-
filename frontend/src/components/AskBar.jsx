export default function AskBar({ question, setQuestion, onAsk, busy, suggestions }) {
  const submit = (e) => {
    e.preventDefault();
    if (!busy && question.trim().length >= 3) onAsk(question.trim());
  };
  return (
    <section aria-label="Ask a question">
      <form className="ask" onSubmit={submit}>
        <label htmlFor="question" className="ask__label">Ask a question about your data</label>
        <div className="ask__row">
          <input
            id="question"
            className="ask__input"
            value={question}
            maxLength={500}
            placeholder="For example: Which region has the highest total revenue?"
            onChange={(e) => setQuestion(e.target.value)}
            disabled={busy}
          />
          <button className="btn btn--primary" type="submit" disabled={busy || question.trim().length < 3}>
            {busy ? "Working…" : "Ask"}
          </button>
        </div>
      </form>
      {suggestions.length > 0 && (
        <ul className="suggest" aria-label="Question ideas">
          {suggestions.map((s) => (
            <li key={s}>
              <button type="button" className="chip" disabled={busy} onClick={() => setQuestion(s)}>{s}</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
