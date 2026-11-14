const LABEL = { ok: "Verified", unverified: "Needs review", failed: "No answer", llm_error: "No answer" };

export default function History({ items, selectedId, onSelect }) {
  if (!items.length) return null;
  return (
    <section className="panel" aria-labelledby="history-heading">
      <h2 id="history-heading" className="panel__title">Earlier questions</h2>
      <ul className="history">
        {items.map((h) => (
          <li key={h.analysis_id}>
            <button
              type="button"
              className={`history__item ${h.analysis_id === selectedId ? "history__item--on" : ""}`}
              onClick={() => onSelect(h.analysis_id)}
            >
              <span className="history__q">{h.question}</span>
              <span className="history__meta">
                {LABEL[h.status] ?? h.status}, {new Date(h.created_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
