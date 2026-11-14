import { useRef, useState } from "react";

export default function UploadPanel({ dataset, uploading, error, onUpload, notice }) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);

  const pick = (file) => file && onUpload(file);

  return (
    <section className="panel" aria-labelledby="dataset-heading">
      <h2 id="dataset-heading" className="panel__title">Your data</h2>

      <label
        className={`drop ${dragging ? "drop--over" : ""} ${dataset ? "drop--compact" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files[0]); }}
      >
        <input
          ref={input}
          type="file"
          className="drop__input"
          accept=".csv,.xlsx,.xls"
          disabled={uploading}
          onChange={(e) => { pick(e.target.files[0]); e.target.value = ""; }}
        />
        <span className="drop__main">
          {uploading ? "Uploading…" : dataset ? "Use a different file" : "Drop a CSV or Excel file here"}
        </span>
        {!dataset && !uploading && <span className="drop__hint">or select one from your computer. Up to 10 MB.</span>}
      </label>

      {notice && <p className="drop__hint panel__note">{notice}</p>}

      {error && <p className="notice notice--error" role="alert">{error}</p>}

      {dataset && (
        <div className="dataset">
          <p className="dataset__name">{dataset.filename}</p>
          <p className="dataset__size">{dataset.rows.toLocaleString()} rows by {dataset.columns.length} columns</p>
          <ul className="columns">
            {dataset.columns.map((c) => (
              <li key={c.name} className="columns__item">
                <span>{c.name}</span>
                <span className="columns__type">{c.dtype}</span>
              </li>
            ))}
          </ul>
          <details className="preview">
            <summary>Preview the first rows</summary>
            <div className="preview__scroll">
              <table>
                <thead>
                  <tr>{dataset.columns.map((c) => <th key={c.name}>{c.name}</th>)}</tr>
                </thead>
                <tbody>
                  {dataset.preview.map((row, i) => (
                    <tr key={i}>{dataset.columns.map((c) => <td key={c.name}>{String(row[c.name] ?? "")}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
