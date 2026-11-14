"""Whitelisted analysis tools. The LLM may only call these, by name,
with JSON arguments. It never writes or executes free-form code."""
from __future__ import annotations
import json
import time
import uuid
from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.express as px


class ToolError(Exception):
    """Raised when a tool gets bad arguments. Message is fed back to the agent."""


# ---------- helpers ----------
def _require_col(df: pd.DataFrame, col: str) -> str:
    if col not in df.columns:
        raise ToolError(f"Column '{col}' not found. Available: {list(df.columns)}")
    return col


def _require_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    _require_col(df, col)
    if not pd.api.types.is_numeric_dtype(df[col]):
        raise ToolError(f"Column '{col}' is not numeric.")
    return df[col].dropna()


def _py(x: Any) -> Any:
    """Convert numpy/pandas scalars to plain JSON-safe Python."""
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if np.isnan(x) else round(float(x), 4)
    if isinstance(x, dict):
        return {str(k): _py(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_py(v) for v in x]
    return x


# ---------- tools ----------
def describe_data(df: pd.DataFrame) -> dict:
    """Row and column counts, column types, missing values and numeric summary."""
    numeric = df.select_dtypes("number")
    return _py({
        "rows": len(df),
        "column_count": int(df.shape[1]),
        "numeric_column_count": int(numeric.shape[1]),
        "missing_total": int(df.isna().sum().sum()),
        "columns": {c: str(t) for c, t in df.dtypes.items()},
        "missing": df.isna().sum().to_dict(),
        "numeric_summary": numeric.describe().T[["mean", "std", "min", "max"]].to_dict("index")
        if not numeric.empty else {},
    })


def group_aggregate(df: pd.DataFrame, group_by: str, column: str, agg: str = "sum") -> dict:
    """Aggregate a numeric column by a category."""
    if agg not in {"sum", "mean", "median", "min", "max", "count"}:
        raise ToolError("agg must be one of sum, mean, median, min, max, count")
    _require_col(df, group_by)
    _require_numeric(df, column)
    out = df.groupby(group_by)[column].agg(agg).sort_values(ascending=False)
    return _py({"group_by": group_by, "column": column, "agg": agg, "values": out.to_dict()})


def top_n(df: pd.DataFrame, column: str, n: int = 5, label: str | None = None,
          ascending: bool = False) -> dict:
    """Top (or bottom) n rows by a numeric column."""
    _require_numeric(df, column)
    n = max(1, min(int(n), 50))
    cols = [column] + ([_require_col(df, label)] if label else [])
    rows = df.nlargest(n, column) if not ascending else df.nsmallest(n, column)
    return _py({"column": column, "ascending": ascending,
                "rows": rows[cols].to_dict("records")})


def correlation(df: pd.DataFrame, col_a: str, col_b: str) -> dict:
    """Pearson correlation between two numeric columns."""
    _require_numeric(df, col_a)
    _require_numeric(df, col_b)
    pair = df[[col_a, col_b]].dropna()
    if len(pair) < 3:
        raise ToolError("Need at least 3 rows with both values.")
    r = float(pair[col_a].corr(pair[col_b]))
    strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
    return _py({"col_a": col_a, "col_b": col_b, "pearson_r": r,
                "strength": strength, "n": len(pair)})


def detect_outliers(df: pd.DataFrame, column: str, method: str = "iqr") -> dict:
    """Flag unusual values using IQR or z-score."""
    s = _require_numeric(df, column)
    if method == "iqr":
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    elif method == "zscore":
        mu, sd = s.mean(), s.std()
        if sd == 0:
            return {"column": column, "method": method, "count": 0, "outliers": []}
        lo, hi = mu - 3 * sd, mu + 3 * sd
    else:
        raise ToolError("method must be 'iqr' or 'zscore'")
    mask = (df[column] < lo) | (df[column] > hi)
    return _py({"column": column, "method": method, "lower_bound": lo,
                "upper_bound": hi, "count": int(mask.sum()),
                "outliers": df.loc[mask, column].head(20).tolist()})


def compare_groups(df: pd.DataFrame, group_by: str, column: str, group_a: str,
                   group_b: str, agg: str = "sum") -> dict:
    """Compare a numeric column between two groups: difference, percent difference ((a-b)/b) and ratio."""
    if agg not in {"sum", "mean", "median", "min", "max", "count"}:
        raise ToolError("agg must be one of sum, mean, median, min, max, count")
    _require_col(df, group_by)
    _require_numeric(df, column)
    values = df.groupby(group_by)[column].agg(agg)
    lookup = {str(k).strip().lower(): k for k in values.index}

    def pick(name: str):
        key = lookup.get(str(name).strip().lower())
        if key is None:
            raise ToolError(f"Group '{name}' not found in '{group_by}'. Available: {list(values.index)[:20]}")
        return key

    ka, kb = pick(group_a), pick(group_b)
    a, b = float(values[ka]), float(values[kb])
    return _py({"group_by": group_by, "column": column, "agg": agg,
                "group_a": str(ka), "value_a": a, "group_b": str(kb), "value_b": b,
                "difference": a - b,
                "percent_difference": None if b == 0 else (a - b) / abs(b) * 100,
                "ratio": None if b == 0 else a / b})


def trend_over_time(df: pd.DataFrame, date_col: str, column: str, freq: str = "M",
                    agg: str = "sum") -> dict:
    """Aggregate a numeric column per period (freq D, W, M, Q or Y). Change, peak and lowest are
    computed on complete periods only. values holds those periods; incomplete first/last periods are
    listed separately in partial_periods (label -> value)."""
    if agg not in {"sum", "mean", "median", "min", "max", "count"}:
        raise ToolError("agg must be one of sum, mean, median, min, max, count")
    if freq not in {"D", "W", "M", "Q", "Y"}:
        raise ToolError("freq must be one of D, W, M, Q, Y")
    _require_col(df, date_col)
    _require_numeric(df, column)
    dates = pd.to_datetime(df[date_col], errors="coerce")
    ok = dates.notna()
    if not ok.any():
        raise ToolError(f"Column '{date_col}' has no valid dates.")
    series = df.loc[ok, column].groupby(dates[ok].dt.to_period(freq)).agg(agg)
    if len(series) > 120:
        raise ToolError(f"{len(series)} periods is too many; use freq M, Q or Y.")

    periods = list(series.index)
    partial = []
    if dates[ok].min().normalize() > periods[0].start_time:
        partial.append(periods[0])
    if dates[ok].max().normalize() < periods[-1].end_time.normalize() and periods[-1] not in partial:
        partial.append(periods[-1])
    complete = series.drop(index=partial)
    base = complete if len(complete) >= 2 else series      # too few complete periods: use everything

    first, last = float(base.iloc[0]), float(base.iloc[-1])
    return _py({"date_col": date_col, "column": column, "freq": freq, "agg": agg,
                "values": {str(k): float(v) for k, v in base.items()},
                "partial_periods": {str(p): float(series[p]) for p in partial},
                "compared_from": str(base.index[0]), "compared_to": str(base.index[-1]),
                "first_value": first, "last_value": last, "change": last - first,
                "percent_change": None if first == 0 else (last - first) / abs(first) * 100,
                "peak_period": str(base.idxmax()), "lowest_period": str(base.idxmin()),
                "invalid_dates_skipped": int((~ok).sum())})


def make_chart(df: pd.DataFrame, kind: str, x: str, y: str | None = None) -> dict:
    """Build a Plotly chart; returns the figure as JSON for the React UI."""
    _require_col(df, x)
    if kind == "hist":
        _require_numeric(df, x)
        fig = px.histogram(df, x=x)
    elif kind in {"bar", "line", "scatter"}:
        if not y:
            raise ToolError(f"'{kind}' chart needs a y column.")
        _require_col(df, y)
        if kind == "bar":
            data = df.groupby(x, as_index=False)[y].sum() if not pd.api.types.is_numeric_dtype(df[x]) else df
            fig = px.bar(data, x=x, y=y)
        elif kind == "line":
            fig = px.line(df.sort_values(x), x=x, y=y)
        else:
            fig = px.scatter(df, x=x, y=y)
    else:
        raise ToolError("kind must be hist, bar, line or scatter")
    return {"kind": kind, "x": x, "y": y, "figure": json.loads(fig.to_json())}


# ---------- registry (this is what the LangGraph agent will see) ----------
TOOLS: dict[str, Callable[..., dict]] = {
    "describe_data": describe_data,
    "group_aggregate": group_aggregate,
    "top_n": top_n,
    "correlation": correlation,
    "detect_outliers": detect_outliers,
    "compare_groups": compare_groups,
    "trend_over_time": trend_over_time,
    "make_chart": make_chart,
}


def run_tool(df: pd.DataFrame, name: str, args: dict | None = None) -> dict:
    """Single entry point. Always returns an evidence record, never raises.
    Every number the agent later reports must trace back to one of these IDs."""
    record = {"id": uuid.uuid4().hex[:8], "tool": name, "args": args or {},
              "ok": False, "result": None, "error": None, "ms": 0}
    start = time.perf_counter()
    try:
        if name not in TOOLS:
            raise ToolError(f"Unknown tool '{name}'. Allowed: {list(TOOLS)}")
        record["result"] = TOOLS[name](df, **(args or {}))
        record["ok"] = True
    except ToolError as exc:
        record["error"] = str(exc)
    except TypeError as exc:   # wrong/missing argument names
        record["error"] = f"Bad arguments: {exc}"
    except Exception as exc:   # last-resort safety net
        record["error"] = f"Unexpected error: {exc}"
    record["ms"] = round((time.perf_counter() - start) * 1000, 2)
    return record
