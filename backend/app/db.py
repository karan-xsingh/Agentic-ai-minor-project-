"""Persistence (Step 4): SQLite for metadata/history, plain files for uploaded datasets."""
from __future__ import annotations
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY, filename TEXT, stored_name TEXT, rows INTEGER,
    columns TEXT, preview TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY, dataset_id TEXT, question TEXT, status TEXT, report TEXT,
    verification TEXT, evidence TEXT, charts TEXT, attempts INTEGER,
    report_attempts INTEGER, duration_ms INTEGER, created_at TEXT);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def public_evidence(evidence: list[dict]) -> list[dict]:
    """Chart figures are big; they travel in `charts`, not inside the evidence trail."""
    out = []
    for e in evidence:
        e = dict(e)
        if e.get("tool") == "make_chart" and isinstance(e.get("result"), dict):
            e["result"] = {k: v for k, v in e["result"].items() if k != "figure"}
        out.append(e)
    return out


class Store:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        (self.dir / "uploads").mkdir(parents=True, exist_ok=True)
        self.db_path = self.dir / "analyst.db"
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        """One short-lived connection per operation: commit on success, rollback on error."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---------- datasets ----------
    def add_dataset(self, filename: str, content: bytes, df: pd.DataFrame) -> dict:
        ds_id = uuid.uuid4().hex[:12]
        ext = "." + filename.lower().rsplit(".", 1)[-1]      # already validated by the loader
        stored = f"{ds_id}{ext}"
        (self.dir / "uploads" / stored).write_bytes(content)
        columns = [{"name": c, "dtype": str(t)} for c, t in df.dtypes.items()]
        preview = json.loads(df.head(5).to_json(orient="records", date_format="iso"))
        with self._conn() as c:
            c.execute("INSERT INTO datasets VALUES (?,?,?,?,?,?,?)",
                      (ds_id, filename, stored, len(df), json.dumps(columns), json.dumps(preview), _now()))
        return self.get_dataset(ds_id)

    def get_dataset(self, ds_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM datasets WHERE id=?", (ds_id,)).fetchone()
        if not row:
            return None
        return {"dataset_id": row["id"], "filename": row["filename"], "rows": row["rows"],
                "columns": json.loads(row["columns"]), "preview": json.loads(row["preview"]),
                "created_at": row["created_at"]}

    def read_bytes(self, ds_id: str) -> bytes:
        with self._conn() as c:
            row = c.execute("SELECT stored_name FROM datasets WHERE id=?", (ds_id,)).fetchone()
        return (self.dir / "uploads" / row["stored_name"]).read_bytes()

    # ---------- analyses ----------
    def add_analysis(self, dataset_id: str, question: str, state: dict, duration_ms: int) -> dict:
        a_id = uuid.uuid4().hex[:12]
        rec = (a_id, dataset_id, question, state.get("status", ""), state.get("report", ""),
               json.dumps(state.get("verification"), default=str),
               json.dumps(public_evidence(state.get("evidence", [])), default=str),
               json.dumps(state.get("charts", []), default=str),
               state.get("attempts", 0), state.get("report_attempts", 0), duration_ms, _now())
        with self._conn() as c:
            c.execute("INSERT INTO analyses VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rec)
        return self.get_analysis(a_id)

    @staticmethod
    def _analysis(row) -> dict:
        return {"analysis_id": row["id"], "dataset_id": row["dataset_id"], "question": row["question"],
                "status": row["status"], "report": row["report"],
                "verification": json.loads(row["verification"]),
                "evidence": json.loads(row["evidence"]), "charts": json.loads(row["charts"]),
                "attempts": row["attempts"], "report_attempts": row["report_attempts"],
                "duration_ms": row["duration_ms"], "created_at": row["created_at"]}

    def get_analysis(self, a_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM analyses WHERE id=?", (a_id,)).fetchone()
        return self._analysis(row) if row else None

    def list_analyses(self, dataset_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM analyses WHERE dataset_id=? ORDER BY created_at DESC, rowid DESC",
                             (dataset_id,)).fetchall()
        out = []
        for r in rows:
            a = self._analysis(r)
            v = a["verification"]
            out.append({"analysis_id": a["analysis_id"], "question": a["question"], "status": a["status"],
                        "verified_score": v["score"] if v else None,
                        "duration_ms": a["duration_ms"], "created_at": a["created_at"]})
        return out
