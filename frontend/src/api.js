// Thin client for the FastAPI backend. Works in the browser and in Node (used by the smoke test).
const env = import.meta.env ?? {};
export const API_BASE = env.VITE_API_URL ?? (env.DEV ? "http://127.0.0.1:8000" : "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function formatDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg ?? JSON.stringify(d)).join("; ");
  return "";
}

async function request(path, options) {
  let res;
  try {
    res = await fetch(API_BASE + path, options);
  } catch {
    throw new ApiError(
      `Cannot reach the backend${API_BASE ? ` at ${API_BASE}` : ""}. Start it with: uvicorn app.main:app --reload`,
      0,
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      detail = formatDetail((await res.json()).detail);
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(detail || `Request failed (${res.status})`, res.status);
  }
  return res.json();
}

export function uploadDataset(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/datasets", { method: "POST", body: form });
}

export const getDataset = (id) => request(`/datasets/${id}`);

export const analyze = (id, question) =>
  request(`/datasets/${id}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

export const listAnalyses = (id) => request(`/datasets/${id}/analyses`);
export const getAnalysis = (id) => request(`/analyses/${id}`);
export const reportUrl = (id) => `${API_BASE}/analyses/${id}/report.md`;

export const getProfile = (id) => request(`/datasets/${id}/profile`);
export const health = () => request("/health");
