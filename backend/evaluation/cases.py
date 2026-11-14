"""Evaluation questions with answers computed independently of the agent's tools.

Ground truth is calculated here with plain pandas/numpy, so a test run compares two separate
implementations. The cases are built from the dataset itself, so they stay correct if the data changes.
"""
from __future__ import annotations
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Case:
    id: str
    category: str
    question: str
    truth: list[float] = field(default_factory=list)       # every number must appear in the report
    mention: list[str] = field(default_factory=list)       # every phrase must appear
    mention_any: list[str] = field(default_factory=list)   # at least one phrase must appear
    tools_any: list[str] = field(default_factory=list)     # at least one of these tools must have run OK
    tools_all: list[str] = field(default_factory=list)     # all of these tools must have run OK
    needs_chart: bool = False
    refusal: bool = False                                  # the data cannot answer it; the agent must say so


def complete_periods(df: pd.DataFrame, date_col: str, value_col: str, freq: str) -> pd.Series:
    """Totals per period, dropping an incomplete first/last period (independent of the app's tool)."""
    dates = pd.to_datetime(df[date_col])
    series = df.groupby(dates.dt.to_period(freq))[value_col].sum()
    drop = []
    if dates.min().normalize() > series.index[0].start_time:
        drop.append(series.index[0])
    if dates.max().normalize() < series.index[-1].end_time.normalize():
        drop.append(series.index[-1])
    return series.drop(index=drop)


def _pct(a: float, b: float) -> float:
    return (a - b) / abs(b) * 100


def _iqr_outliers(s: pd.Series) -> int:
    q1, q3 = s.quantile([0.25, 0.75])
    return int(((s < q1 - 1.5 * (q3 - q1)) | (s > q3 + 1.5 * (q3 - q1))).sum())


def build_cases(df: pd.DataFrame) -> list[Case]:
    rev_region = df.groupby("region")["revenue"].sum()
    rev_product = df.groupby("product")["revenue"].sum()
    units_product = df.groupby("product")["units"].mean()
    orders_region = df.groupby("region")["revenue"].count()
    quarterly = complete_periods(df, "order_date", "revenue", "Q")
    monthly = complete_periods(df, "order_date", "revenue", "M")
    year_2025 = df[pd.to_datetime(df["order_date"]).dt.year == 2025]["revenue"].sum()
    units_mean = df.groupby("region")["units"].mean()
    top3 = df["revenue"].nlargest(3).tolist()
    out_rev = _iqr_outliers(df["revenue"])
    out_units = _iqr_outliers(df["units"])
    missing = int(df.isna().sum().sum())

    cases = [
        # --- aggregation ---
        Case("A1", "aggregation", "Which region has the highest total revenue?",
             truth=[rev_region.max()], mention=[rev_region.idxmax()], tools_any=["group_aggregate"]),
        Case("A2", "aggregation", "Which region has the lowest total revenue?",
             truth=[rev_region.min()], mention=[rev_region.idxmin()], tools_any=["group_aggregate"]),
        Case("A3", "aggregation", "Which product sells the most units on average per order?",
             truth=[units_product.max()], mention=[units_product.idxmax()], tools_any=["group_aggregate"]),
        Case("A4", "aggregation", "What is the average revenue per order?",
             truth=[df["revenue"].mean()], tools_any=["describe_data", "group_aggregate"]),
        Case("A5", "aggregation", "How many orders does each region have?",
             truth=[orders_region.max(), orders_region.min()],
             mention=[orders_region.idxmax(), orders_region.idxmin()], tools_any=["group_aggregate"]),
        Case("A6", "aggregation", "Which product earns the most total revenue?",
             truth=[rev_product.max()], mention=[rev_product.idxmax()], tools_any=["group_aggregate"]),
        Case("A7", "aggregation", "What is the total revenue from Laptop orders?",
             truth=[rev_product["Laptop"]], tools_any=["group_aggregate", "compare_groups"]),
        # --- comparison ---
        Case("C1", "comparison", "How much higher is North revenue than South revenue, in percent?",
             truth=[_pct(rev_region["North"], rev_region["South"])], tools_any=["compare_groups"]),
        Case("C2", "comparison", "Compare total revenue of Phone and Tablet. How many percent higher is Phone?",
             truth=[_pct(rev_product["Phone"], rev_product["Tablet"])], tools_any=["compare_groups"]),
        Case("C3", "comparison", "By what percent is the average units per order in East higher than in West?",
             truth=[_pct(units_mean["East"], units_mean["West"])], tools_any=["compare_groups"]),
        # --- ranking ---
        Case("R1", "ranking", "Show the three biggest orders by revenue.",
             truth=top3, tools_any=["top_n"]),
        Case("R2", "ranking", "What is the smallest order by revenue?",
             truth=[df["revenue"].min()], tools_any=["top_n"]),
        # --- correlation ---
        Case("K1", "correlation", "Are units and revenue correlated?",
             truth=[df["units"].corr(df["revenue"])], tools_any=["correlation"]),
        # --- outliers ---
        Case("O1", "outliers", "Are there any unusual revenue values?",
             truth=[out_rev] if out_rev else [], mention_any=[] if out_rev else ["no ", "none", "zero", "0"],
             tools_any=["detect_outliers"]),
        Case("O2", "outliers", "Are there any unusual units values?",
             truth=[out_units] if out_units else [], mention_any=[] if out_units else ["no ", "none", "zero", "0", "not find", "did not"],
             tools_any=["detect_outliers"]),
        # --- trends ---
        Case("T1", "trend", "How did quarterly revenue change from the first to the last complete quarter, in percent?",
             truth=[_pct(quarterly.iloc[-1], quarterly.iloc[0])], tools_any=["trend_over_time"]),
        Case("T2", "trend", "Which complete month had the highest revenue, and how much was it?",
             truth=[monthly.max()], tools_any=["trend_over_time"]),
        Case("T3", "trend", "What was the total revenue in 2025?",
             truth=[year_2025], tools_any=["trend_over_time"]),
        # --- descriptive ---
        Case("D1", "descriptive", "Give me an overview of this dataset.",
             truth=[len(df)], tools_any=["describe_data"]),
        Case("D2", "descriptive", "Are there any missing values?",
             truth=[missing] if missing else [], mention_any=[] if missing else ["no missing", "none", "zero", "0 missing", "missing values: 0", "missing: 0", "no null", "no empty", "complete", "nothing is missing", "not missing", "no values are missing", "without any missing"],
             tools_any=["describe_data"]),
        Case("D3", "descriptive", "What columns does the dataset have?",
             mention=list(df.columns), tools_any=["describe_data"]),
        # --- chart ---
        Case("G1", "chart", "Show a bar chart of total revenue by region.",
             needs_chart=True, tools_all=["make_chart"]),
        # --- unanswerable: the honest answer is "the data cannot tell us" ---
        Case("U1", "unanswerable", "What is the profit margin of each product?", refusal=True),
        Case("U2", "unanswerable", "Which customer spent the most money?", refusal=True),
        Case("U3", "unanswerable", "Forecast the revenue for next quarter.", refusal=True),
    ]
    return cases
