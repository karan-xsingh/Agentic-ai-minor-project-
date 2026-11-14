import pandas as pd
import pytest
from app.loader import load_dataset, DatasetError
from app.tools import run_tool


@pytest.fixture
def df():
    return pd.DataFrame({
        "region": ["N", "N", "S", "S", "E"],
        "sales": [100, 200, 50, 150, 1000],
        "units": [1, 2, 1, 3, 10],
    })


def test_group_sum_matches_pandas(df):
    r = run_tool(df, "group_aggregate", {"group_by": "region", "column": "sales", "agg": "sum"})
    assert r["ok"] and r["result"]["values"] == {"E": 1000, "N": 300, "S": 200}


def test_top_n(df):
    r = run_tool(df, "top_n", {"column": "sales", "n": 1, "label": "region"})
    assert r["result"]["rows"][0]["region"] == "E"


def test_correlation_strong(df):
    r = run_tool(df, "correlation", {"col_a": "sales", "col_b": "units"})
    assert r["result"]["strength"] == "strong"


def test_outlier_detected(df):
    r = run_tool(df, "detect_outliers", {"column": "sales"})
    assert r["result"]["count"] == 1 and r["result"]["outliers"] == [1000]


def test_chart_returns_figure(df):
    r = run_tool(df, "make_chart", {"kind": "bar", "x": "region", "y": "sales"})
    assert r["ok"] and "data" in r["result"]["figure"]


def test_bad_column_fails_safely(df):
    r = run_tool(df, "group_aggregate", {"group_by": "nope", "column": "sales"})
    assert not r["ok"] and "not found" in r["error"]


def test_unknown_tool_blocked(df):
    r = run_tool(df, "os_system", {"cmd": "ls"})
    assert not r["ok"] and "Unknown tool" in r["error"]


def test_wrong_args_fail_safely(df):
    r = run_tool(df, "top_n", {"bogus": 1})
    assert not r["ok"]


def test_loader_rejects_bad_extension():
    with pytest.raises(DatasetError):
        load_dataset(b"x", "malware.exe")


def test_loader_cleans_columns():
    df = load_dataset(b"Order Date,Net Revenue ($)\n2025-01-01,5\n", "a.csv")
    assert list(df.columns) == ["order_date", "net_revenue"]


# ---------- compare_groups / trend_over_time ----------
@pytest.fixture
def tdf():
    return pd.DataFrame({
        "order_date": ["2025-01-05", "2025-01-20", "2025-02-10", "2025-03-01", "not a date"],
        "region": ["North", "South", "North", "South", "North"],
        "sales": [100, 50, 200, 100, 10],
    })


def test_compare_groups_percent_difference(tdf):
    r = run_tool(tdf, "compare_groups", {"group_by": "region", "column": "sales",
                                         "group_a": "north", "group_b": "SOUTH"})   # case-insensitive
    res = r["result"]
    assert r["ok"] and res["value_a"] == 310 and res["value_b"] == 150
    assert res["difference"] == 160 and res["percent_difference"] == pytest.approx(106.6667, abs=1e-3)


def test_compare_groups_unknown_group(tdf):
    r = run_tool(tdf, "compare_groups", {"group_by": "region", "column": "sales",
                                         "group_a": "North", "group_b": "Mars"})
    assert not r["ok"] and "Available" in r["error"]


def test_trend_monthly(tdf):
    r = run_tool(tdf, "trend_over_time", {"date_col": "order_date", "column": "sales", "freq": "M"})
    res = r["result"]
    assert r["ok"] and res["values"] == {"2025-01": 150, "2025-02": 200, "2025-03": 100}
    assert res["peak_period"] == "2025-02" and res["percent_change"] == pytest.approx(-33.3333, abs=1e-3)
    assert res["invalid_dates_skipped"] == 1 and res["partial_periods"] == {"2025-01": 150, "2025-03": 100}


def test_trend_rejects_bad_inputs(tdf):
    assert not run_tool(tdf, "trend_over_time", {"date_col": "region", "column": "sales"})["ok"]
    assert not run_tool(tdf, "trend_over_time", {"date_col": "order_date", "column": "sales", "freq": "X"})["ok"]


def test_trend_excludes_partial_last_period():
    df = pd.DataFrame({
        "d": ["2025-01-01", "2025-01-31", "2025-02-01", "2025-02-28",
              "2025-03-01", "2025-03-31", "2025-04-01"],
        "v": [100, 100, 150, 150, 300, 300, 10]})
    res = run_tool(df, "trend_over_time", {"date_col": "d", "column": "v", "freq": "M"})["result"]
    assert res["partial_periods"] == {"2025-04": 10}
    assert res["compared_from"] == "2025-01" and res["compared_to"] == "2025-03"
    assert res["change"] == 400 and res["percent_change"] == 200
    assert res["peak_period"] == "2025-03" and res["lowest_period"] == "2025-01"
    assert "2025-04" not in res["values"]          # partial period is kept out of the comparison


def test_describe_data_reports_the_counts_a_report_will_quote(df):
    res = run_tool(df, "describe_data", {})["result"]
    assert res["rows"] == 5 and res["column_count"] == 3 and res["numeric_column_count"] == 2
    assert res["missing_total"] == 0
