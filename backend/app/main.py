"""FastAPI backend (Step 4).

Run:   uvicorn app.main:app --reload        then open http://127.0.0.1:8000/docs
"""
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import loader
from .agent import run_agent
from .db import Store
from .limits import Limits, RateLimiter, visitor_address
from .llm import LLM, LLMError, make_llm
from .profile import profile_dataset
from .report import build_markdown

CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]   # Vite dev server
DEFAULT_UI_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"   # created by `npm run build`


class AnalyzeRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


def create_app(data_dir: str | Path | None = None,
               llm_factory: Callable[[], LLM] = make_llm,
               ui_dir: str | Path | None = None,
               limits: Limits | None = None) -> FastAPI:
    store = Store(Path(data_dir or os.getenv("ANALYST_DATA_DIR", "storage")))
    app = FastAPI(title="Agentic Data Analyst", version="0.8")

    # Extra browser origins (for example your Vercel address) come from ALLOWED_ORIGINS, comma separated.
    extra = [o.strip().rstrip("/") for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS + extra,
                       allow_methods=["*"], allow_headers=["*"])

    limits = limits or Limits.from_env()
    limiter = RateLimiter(limits)

    def enforce(kind: str, request: Request) -> None:
        allowed, wait, reason = limiter.check(kind, visitor_address(request, limits.trust_proxy))
        if not allowed:
            raise HTTPException(status_code=429, detail=reason, headers={"Retry-After": str(wait)})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/datasets")
    def upload_dataset(request: Request, file: UploadFile = File(...)):
        enforce("upload", request)
        content = file.file.read(loader.MAX_BYTES + 1)         # never read more than the limit
        try:
            df = loader.load_dataset(content, file.filename or "")
        except loader.DatasetError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return store.add_dataset(file.filename, content, df)

    @app.get("/datasets/{dataset_id}")
    def get_dataset(dataset_id: str):
        ds = store.get_dataset(dataset_id)
        if not ds:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return ds

    @app.get("/datasets/{dataset_id}/profile")
    def dataset_profile(dataset_id: str):
        ds = store.get_dataset(dataset_id)
        if not ds:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return profile_dataset(loader.load_dataset(store.read_bytes(dataset_id), ds["filename"]))

    @app.post("/datasets/{dataset_id}/analyze")
    def analyze(dataset_id: str, body: AnalyzeRequest, request: Request):
        ds = store.get_dataset(dataset_id)
        if not ds:
            raise HTTPException(status_code=404, detail="Dataset not found")
        enforce("analyze", request)
        try:
            llm = llm_factory()
        except LLMError as exc:
            raise HTTPException(status_code=503, detail=f"LLM not configured: {exc}")
        question = body.question.strip()
        df = loader.load_dataset(store.read_bytes(dataset_id), ds["filename"])
        started = time.perf_counter()
        state = run_agent(df, question, llm)
        return store.add_analysis(dataset_id, question, state,
                                  int((time.perf_counter() - started) * 1000))

    @app.get("/datasets/{dataset_id}/analyses")
    def list_analyses(dataset_id: str):
        if not store.get_dataset(dataset_id):
            raise HTTPException(status_code=404, detail="Dataset not found")
        return store.list_analyses(dataset_id)

    @app.get("/analyses/{analysis_id}")
    def get_analysis(analysis_id: str):
        analysis = store.get_analysis(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return analysis

    @app.get("/analyses/{analysis_id}/report.md")
    def download_report(analysis_id: str):
        analysis = store.get_analysis(analysis_id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        md = build_markdown(analysis, store.get_dataset(analysis["dataset_id"]))
        return PlainTextResponse(md, media_type="text/markdown",
                                 headers={"Content-Disposition": f'attachment; filename="report-{analysis_id}.md"'})

    # If the React app has been built, serve it from the same address (one command to run everything).
    ui = Path(ui_dir) if ui_dir is not None else DEFAULT_UI_DIR
    if (ui / "index.html").exists():
        app.mount("/", StaticFiles(directory=ui, html=True), name="ui")

    return app


app = create_app()
