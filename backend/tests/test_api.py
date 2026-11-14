import json
import re
import pytest
from fastapi.testclient import TestClient

from app.llm import LLMError
from app.main import create_app

CSV = b"region,sales\nN,100\nN,200\nS,50\nS,150\n"
PLAN = json.dumps({"steps": [{"tool": "group_aggregate",
                              "args": {"group_by": "region", "column": "sales", "agg": "sum"}}]})
CHART_PLAN = json.dumps({"steps": [
    {"tool": "group_aggregate", "args": {"group_by": "region", "column": "sales", "agg": "sum"}},
    {"tool": "make_chart", "args": {"kind": "bar", "x": "region", "y": "sales"}}]})


def fake_llm(plan=PLAN):
    def llm(system, user):
        if "PLANNER" in system:
            return plan
        ids = re.findall(r'"id": "(\w{8})"', user)
        gid = [i for i in ids][1]                      # id of the group_aggregate evidence
        return f"N total is 300 [E:{gid}]"
    return llm


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path, llm_factory=lambda: fake_llm()))


def upload(client, content=CSV, name="sales.csv"):
    return client.post("/datasets", files={"file": (name, content, "text/csv")})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_returns_summary(client):
    r = upload(client)
    body = r.json()
    assert r.status_code == 200 and body["rows"] == 4 and body["filename"] == "sales.csv"
    assert [c["name"] for c in body["columns"]] == ["region", "sales"] and len(body["preview"]) == 4
    assert client.get(f"/datasets/{body['dataset_id']}").json()["rows"] == 4


@pytest.mark.parametrize("content,name", [(b"x", "virus.exe"), (b"", "empty.csv"), (b"a,b\n", "headers_only.csv")])
def test_upload_rejects_bad_files(client, content, name):
    r = upload(client, content, name)
    assert r.status_code == 400 and r.json()["detail"]


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr("app.loader.MAX_BYTES", 100)
    r = upload(client, b"a,b\n" + b"1,2\n" * 200)
    assert r.status_code == 400 and "too large" in r.json()["detail"]


def test_analyze_end_to_end_and_persistence(client):
    ds = upload(client).json()["dataset_id"]
    r = client.post(f"/datasets/{ds}/analyze", json={"question": "total sales by region?"})
    a = r.json()
    assert r.status_code == 200 and a["status"] == "ok"
    assert a["verification"]["passed"] and a["verification"]["score"] == 1.0
    assert any(e["tool"] == "group_aggregate" and e["ok"] for e in a["evidence"])

    assert client.get(f"/analyses/{a['analysis_id']}").json()["report"] == a["report"]
    history = client.get(f"/datasets/{ds}/analyses").json()
    assert len(history) == 1 and history[0]["verified_score"] == 1.0


def test_chart_goes_in_charts_not_evidence(tmp_path):
    client = TestClient(create_app(tmp_path, llm_factory=lambda: fake_llm(CHART_PLAN)))
    ds = upload(client).json()["dataset_id"]
    a = client.post(f"/datasets/{ds}/analyze", json={"question": "chart sales by region"}).json()
    assert len(a["charts"]) == 1 and "data" in a["charts"][0]["figure"]
    chart_evidence = [e for e in a["evidence"] if e["tool"] == "make_chart"][0]
    assert "figure" not in chart_evidence["result"]


def test_history_survives_restart(tmp_path):
    first = TestClient(create_app(tmp_path, llm_factory=lambda: fake_llm()))
    ds = upload(first).json()["dataset_id"]
    aid = first.post(f"/datasets/{ds}/analyze", json={"question": "total sales?"}).json()["analysis_id"]
    second = TestClient(create_app(tmp_path, llm_factory=lambda: fake_llm()))    # new process, same folder
    assert second.get(f"/analyses/{aid}").status_code == 200
    again = second.post(f"/datasets/{ds}/analyze", json={"question": "total sales again?"})
    assert again.status_code == 200 and len(second.get(f"/datasets/{ds}/analyses").json()) == 2


def test_markdown_report_download(client):
    ds = upload(client).json()["dataset_id"]
    aid = client.post(f"/datasets/{ds}/analyze", json={"question": "total sales by region?"}).json()["analysis_id"]
    r = client.get(f"/analyses/{aid}/report.md")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    for part in ("# Data analysis report", "total sales by region?", "## Verification", "group_aggregate"):
        assert part in r.text


def test_not_found_and_validation(client):
    assert client.get("/datasets/nope").status_code == 404
    assert client.get("/analyses/nope").status_code == 404
    assert client.get("/analyses/nope/report.md").status_code == 404
    assert client.post("/datasets/nope/analyze", json={"question": "hello there"}).status_code == 404
    ds = upload(client).json()["dataset_id"]
    assert client.post(f"/datasets/{ds}/analyze", json={"question": "x"}).status_code == 422
    assert client.post(f"/datasets/{ds}/analyze", json={"question": "x" * 501}).status_code == 422


def test_llm_not_configured_gives_503(tmp_path):
    def broken():
        raise LLMError("GROQ_API_KEY is not set")
    client = TestClient(create_app(tmp_path, llm_factory=broken))
    ds = upload(client).json()["dataset_id"]
    r = client.post(f"/datasets/{ds}/analyze", json={"question": "total sales?"})
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["detail"]


def test_cors_allows_react_dev_server(client):
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_serves_built_ui_without_hiding_the_api(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<html><body>React app</body></html>")
    client = TestClient(create_app(tmp_path / "data", llm_factory=lambda: fake_llm(), ui_dir=ui))
    assert "React app" in client.get("/").text
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    assert upload(client).status_code == 200


def test_no_ui_folder_means_plain_api(tmp_path):
    client = TestClient(create_app(tmp_path, llm_factory=lambda: fake_llm(), ui_dir=tmp_path / "missing"))
    assert client.get("/").status_code == 404
    assert client.get("/health").status_code == 200
