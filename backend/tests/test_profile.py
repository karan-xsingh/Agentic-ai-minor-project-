import pandas as pd
from fastapi.testclient import TestClient

from app.main import create_app
from app.profile import profile_dataset

DF = pd.DataFrame({
    "order_date": ["2025-01-01", "2025-02-15", "2025-03-31", "2025-03-31"],
    "region": ["N", "N", "S", None],
    "units": [1, 2, 3, 10],
    "revenue": [10.5, 20.0, None, 40.0],
})


def test_overview_numbers():
    p = profile_dataset(DF)
    assert (p["rows"], p["columns"], p["missing_total"], p["numeric_columns"]) == (4, 4, 2, 2)


def test_column_kinds_are_detected():
    kinds = {c["name"]: c["kind"] for c in profile_dataset(DF)["profile"]}
    assert kinds == {"order_date": "date", "region": "category", "units": "number", "revenue": "number"}


def test_number_column_stats_and_histogram():
    col = {c["name"]: c for c in profile_dataset(DF)["profile"]}["units"]
    assert (col["min"], col["max"], col["mean"], col["median"]) == (1, 10, 4, 2.5)
    assert sum(col["hist"]["counts"]) == 4 and len(col["hist"]["edges"]) == len(col["hist"]["counts"]) + 1


def test_missing_values_are_not_counted_in_histogram():
    col = {c["name"]: c for c in profile_dataset(DF)["profile"]}["revenue"]
    assert col["missing"] == 1 and sum(col["hist"]["counts"]) == 3


def test_category_top_values_and_date_range():
    cols = {c["name"]: c for c in profile_dataset(DF)["profile"]}
    assert cols["region"]["top"] == [{"value": "N", "count": 2}, {"value": "S", "count": 1}]
    assert cols["region"]["missing"] == 1
    assert (cols["order_date"]["min"], cols["order_date"]["max"], cols["order_date"]["span_days"]) == ("2025-01-01", "2025-03-31", 89)


def test_profile_endpoint(tmp_path):
    client = TestClient(create_app(tmp_path, llm_factory=lambda: None))
    ds = client.post("/datasets", files={"file": ("d.csv", b"region,sales\nN,100\nS,50\n", "text/csv")}).json()["dataset_id"]
    body = client.get(f"/datasets/{ds}/profile").json()
    assert body["rows"] == 2 and body["profile"][1]["kind"] == "number"
    assert client.get("/datasets/nope/profile").status_code == 404
