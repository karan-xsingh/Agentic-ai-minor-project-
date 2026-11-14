import pytest
from fastapi.testclient import TestClient

from app.limits import Limits, RateLimiter
from app.main import create_app

CSV = b"region,sales\nN,100\nS,50\n"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_hourly_limit_blocks_then_recovers():
    clock = Clock()
    rl = RateLimiter(Limits(analyze_per_hour=2), clock)
    assert rl.check("analyze", "a")[0] and rl.check("analyze", "a")[0]
    allowed, wait, why = rl.check("analyze", "a")
    assert not allowed and 0 < wait <= 3600 and "2 questions per hour" in why
    clock.now += 3601
    assert rl.check("analyze", "a")[0]


def test_each_visitor_has_their_own_allowance():
    rl = RateLimiter(Limits(analyze_per_hour=1))
    assert rl.check("analyze", "a")[0] and rl.check("analyze", "b")[0]
    assert not rl.check("analyze", "a")[0]


def test_daily_total_protects_the_ai_key_across_visitors():
    rl = RateLimiter(Limits(analyze_per_day_total=2))
    assert rl.check("analyze", "a")[0] and rl.check("analyze", "b")[0]
    allowed, _, why = rl.check("analyze", "c")
    assert not allowed and "daily" in why


def test_blocked_requests_do_not_use_up_the_daily_total():
    rl = RateLimiter(Limits(analyze_per_hour=1, analyze_per_day_total=2))
    assert rl.check("analyze", "a")[0]
    assert not rl.check("analyze", "a")[0]          # blocked by the hourly limit
    assert rl.check("analyze", "b")[0]              # the total still had room for this one


def test_no_limits_by_default():
    rl = RateLimiter(Limits())
    assert all(rl.check("analyze", "a")[0] for _ in range(500))


def test_limits_read_from_environment(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ANALYZE_PER_HOUR", "7")
    monkeypatch.setenv("GLOBAL_ANALYZE_PER_DAY", "oops")      # bad values fall back to "no limit"
    monkeypatch.setenv("TRUST_PROXY", "1")
    lim = Limits.from_env()
    assert (lim.analyze_per_hour, lim.analyze_per_day_total, lim.trust_proxy) == (7, 0, True)


# ---------------- through the real API ----------------
def api(tmp_path, **kw):
    return TestClient(create_app(tmp_path, llm_factory=lambda: (lambda system, user: '{"steps":[]}'), limits=Limits(**kw)))


def test_api_returns_429_with_a_friendly_message(tmp_path):
    c = api(tmp_path, analyze_per_hour=1)
    ds = c.post("/datasets", files={"file": ("d.csv", CSV, "text/csv")}).json()["dataset_id"]
    assert c.post(f"/datasets/{ds}/analyze", json={"question": "first question"}).status_code == 200
    r = c.post(f"/datasets/{ds}/analyze", json={"question": "second question"})
    assert r.status_code == 429 and "per hour" in r.json()["detail"] and "retry-after" in r.headers


def test_uploads_have_their_own_limit(tmp_path):
    c = api(tmp_path, upload_per_hour=1)
    f = {"file": ("d.csv", CSV, "text/csv")}
    assert c.post("/datasets", files=f).status_code == 200
    assert c.post("/datasets", files=f).status_code == 429


def test_proxy_header_separates_visitors_only_when_trusted(tmp_path):
    def run(trust):
        c = api(tmp_path / str(trust), analyze_per_hour=1, trust_proxy=trust)
        ds = c.post("/datasets", files={"file": ("d.csv", CSV, "text/csv")}).json()["dataset_id"]
        codes = [c.post(f"/datasets/{ds}/analyze", json={"question": "a question"}, headers={"X-Forwarded-For": ip}).status_code
                 for ip in ("1.1.1.1", "2.2.2.2")]
        return codes
    assert run(True) == [200, 200]       # two different visitors behind the proxy
    assert run(False) == [200, 429]      # header ignored: both look like one visitor


def test_health_and_reading_are_never_limited(tmp_path):
    c = api(tmp_path, analyze_per_hour=1, upload_per_hour=1)
    assert all(c.get("/health").status_code == 200 for _ in range(30))


def test_extra_cors_origin_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://my-app.vercel.app/, https://other.example.com")
    c = TestClient(create_app(tmp_path, llm_factory=lambda: None))
    ok = c.get("/health", headers={"Origin": "https://my-app.vercel.app"})
    assert ok.headers.get("access-control-allow-origin") == "https://my-app.vercel.app"
    bad = c.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in bad.headers
