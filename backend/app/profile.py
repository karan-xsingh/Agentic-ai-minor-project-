"""Dataset overview (no LLM): what the data looks like before any question is asked."""
from __future__ import annotations
import re

import numpy as np
import pandas as pd


def _num(x) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), 4)


def _parse_dates(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", format="mixed")


def _kind(s: pd.Series, name: str) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "category"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "date"
    if pd.api.types.is_numeric_dtype(s):
        return "number"
    if re.search(r"date|time", name, re.I) and _parse_dates(s).notna().mean() >= 0.9:
        return "date"
    return "category"


def _column(df: pd.DataFrame, name: str) -> dict:
    s = df[name]
    kind = _kind(s, name)
    out = {"name": name, "kind": kind, "missing": int(s.isna().sum()), "unique": int(s.nunique())}

    if kind == "number":
        v = s.dropna().astype(float)
        if len(v):
            counts, edges = np.histogram(v, bins=min(10, max(1, int(v.nunique()))))
            out["hist"] = {"counts": [int(c) for c in counts], "edges": [_num(e) for e in edges]}
        out.update(min=_num(v.min()) if len(v) else None, max=_num(v.max()) if len(v) else None,
                   mean=_num(v.mean()) if len(v) else None, median=_num(v.median()) if len(v) else None)
    elif kind == "date":
        d = _parse_dates(s).dropna()
        out.update(min=d.min().date().isoformat() if len(d) else None,
                   max=d.max().date().isoformat() if len(d) else None,
                   span_days=int((d.max() - d.min()).days) if len(d) else None)
    else:
        top = s.value_counts(dropna=True).head(5)
        out["top"] = [{"value": str(k), "count": int(c)} for k, c in top.items()]
    return out


def profile_dataset(df: pd.DataFrame) -> dict:
    columns = [_column(df, c) for c in df.columns]
    return {
        "rows": int(len(df)),
        "columns": len(columns),
        "missing_total": int(df.isna().sum().sum()),
        "numeric_columns": sum(c["kind"] == "number" for c in columns),
        "profile": columns,
    }
