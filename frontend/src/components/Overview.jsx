import { formatStat } from "../lib/report.js";

function Histogram({ hist }) {
  const { counts, edges } = hist;
  const max = Math.max(...counts, 1);
  const w = 200;
  const h = 52;
  const gap = 2;
  const bar = (w - gap * (counts.length - 1)) / counts.length;
  return (
    <svg className="hist" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Distribution of values" preserveAspectRatio="none">
      {counts.map((c, i) => {
        const bh = Math.max(c ? 2 : 0, (c / max) * h);
        return (
          <rect key={i} x={i * (bar + gap)} y={h - bh} width={bar} height={bh} rx="1.5">
            <title>{`${formatStat(edges[i])} to ${formatStat(edges[i + 1])}: ${c.toLocaleString("en-US")} rows`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

function TopValues({ top, rows }) {
  const max = Math.max(...top.map((t) => t.count), 1);
  return (
    <ul className="topvals">
      {top.map((t) => (
        <li key={t.value} className="topvals__row">
          <span className="topvals__label">{t.value}</span>
          <span className="topvals__track"><span className="topvals__fill" style={{ width: `${(t.count / max) * 100}%` }} /></span>
          <span className="topvals__count" title={`${((t.count / rows) * 100).toFixed(1)}% of rows`}>{t.count.toLocaleString("en-US")}</span>
        </li>
      ))}
    </ul>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Column({ c, rows }) {
  return (
    <article className="col">
      <header className="col__head">
        <h4 className="col__name">{c.name}</h4>
        <span className="col__kind">{c.kind}</span>
      </header>

      {c.kind === "number" && c.hist && (
        <>
          <Histogram hist={c.hist} />
          <dl className="stats">
            <Stat label="lowest" value={formatStat(c.min)} />
            <Stat label="average" value={formatStat(c.mean)} />
            <Stat label="highest" value={formatStat(c.max)} />
          </dl>
        </>
      )}
      {c.kind === "date" && (
        <dl className="stats stats--wide">
          <Stat label="from" value={c.min ?? "n/a"} />
          <Stat label="to" value={c.max ?? "n/a"} />
          <Stat label="days covered" value={formatStat(c.span_days)} />
        </dl>
      )}
      {c.kind === "category" && (
        <>
          <TopValues top={c.top} rows={rows} />
          <p className="col__note">{c.unique.toLocaleString("en-US")} different {c.unique === 1 ? "value" : "values"}{c.unique > c.top.length ? `, top ${c.top.length} shown` : ""}</p>
        </>
      )}
      {c.missing > 0 && <p className="col__missing">{c.missing.toLocaleString("en-US")} missing</p>}
    </article>
  );
}

export default function Overview({ profile, open }) {
  if (!profile) return null;
  const kpis = [
    { label: "rows", value: profile.rows.toLocaleString("en-US") },
    { label: "columns", value: profile.columns.toLocaleString("en-US") },
    { label: "numeric columns", value: profile.numeric_columns.toLocaleString("en-US") },
    { label: "missing values", value: profile.missing_total === 0 ? "None" : profile.missing_total.toLocaleString("en-US"), good: profile.missing_total === 0 },
  ];
  return (
    <details className="overview" open={open}>
      <summary className="overview__summary">What is in this data</summary>
      <dl className="kpis">
        {kpis.map((k) => (
          <div key={k.label} className="kpi">
            <dd className={`kpi__value ${k.good ? "kpi__value--good" : ""}`}>{k.value}</dd>
            <dt className="kpi__label">{k.label}</dt>
          </div>
        ))}
      </dl>
      <div className="cols">
        {profile.profile.map((c) => <Column key={c.name} c={c} rows={profile.rows} />)}
      </div>
    </details>
  );
}
