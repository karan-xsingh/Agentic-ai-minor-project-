"""Safe dataset loading and validation (Step 1)."""
from __future__ import annotations
import io
import pandas as pd

ALLOWED_EXT = {".csv", ".xlsx", ".xls"}
MAX_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_ROWS = 200_000
MAX_COLS = 100


class DatasetError(Exception):
    """Raised for any invalid upload. Message is safe to show to the user."""


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.astype(str).str.strip().str.lower()
        .str.replace(r"[^0-9a-zA-Z]+", "_", regex=True).str.strip("_")
    )
    if df.columns.duplicated().any():
        raise DatasetError("Duplicate column names after cleaning.")
    return df


def load_dataset(content: bytes, filename: str) -> pd.DataFrame:
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise DatasetError(f"Unsupported file type '{ext}'. Use CSV or Excel.")
    if len(content) == 0:
        raise DatasetError("File is empty.")
    if len(content) > MAX_BYTES:
        raise DatasetError("File too large (max 10 MB).")

    try:
        buf = io.BytesIO(content)
        df = pd.read_csv(buf) if ext == ".csv" else pd.read_excel(buf)
    except Exception as exc:  # parser errors vary widely
        raise DatasetError(f"Could not read file: {exc}") from exc

    if df.empty:
        raise DatasetError("Dataset has no rows.")
    if len(df) > MAX_ROWS or df.shape[1] > MAX_COLS:
        raise DatasetError("Dataset too large (max 200,000 rows / 100 columns).")

    return _clean_columns(df)
