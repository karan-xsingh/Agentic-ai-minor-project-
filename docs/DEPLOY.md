# Putting the project online

Two parts, because they need different kinds of hosting:

| Part | Where | Why |
|---|---|---|
| React interface | Vercel | Static files, which Vercel is built for |
| Python backend (agent, database, uploads) | Render (Docker) | Needs a real server, a writable disk, and requests that take 10 to 20 seconds |

Vercel's serverless functions have a read-only disk and short time limits, so they are a poor fit for the backend.

**Shortcut:** the Docker container already serves the interface too. After Part 2 below, the Render address
alone is a working public link. Part 3 (Vercel) just gives you a second address with the interface on Vercel.

## Before you start

1. **Create a new API key** for the deployment (in the Groq console). Do not reuse a key you have ever pasted anywhere.
   Keep it only in the hosting dashboard. Never put it in GitHub, in `.env` files that are committed, or in Vercel.
2. Anything starting with `VITE_` is visible to every visitor. Only the backend address goes there.
3. A public link lets strangers use your AI quota. The settings below limit that.

## Part 1: GitHub

```powershell
cd $HOME\agentic-analyst
git init
git add .
git status
git check-ignore -v backend/.env
git grep -nE "gsk_|AIza|sk-[A-Za-z0-9]{20}"
git commit -m "Agentic Data Analyst"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git push -u origin main
```

`git status` must not list `.env`. `git grep` must print nothing.

## Part 2: Backend on Render

1. Sign in at render.com with GitHub. New, then Web Service, then choose your repository.
2. Language (runtime): **Docker**. Branch: `main`. Leave Root Directory empty.
3. Instance type: the free one is enough for a demo.
4. Health Check Path: `/health`
5. Environment variables:

| Name | Value |
|---|---|
| `LLM_PROVIDER` | `groq` |
| `GROQ_API_KEY` | your new key |
| `LLM_MODEL` | `openai/gpt-oss-120b` |
| `TRUST_PROXY` | `1` |
| `RATE_LIMIT_ANALYZE_PER_HOUR` | `20` |
| `RATE_LIMIT_UPLOAD_PER_HOUR` | `20` |
| `GLOBAL_ANALYZE_PER_DAY` | `300` |

6. Create the service and wait for the build (several minutes the first time).
7. Open `https://YOUR-SERVICE.onrender.com/health`. You should see `{"status":"ok"}`. Opening the address without
   `/health` shows the full app.

## Part 3: Interface on Vercel

1. Sign in at vercel.com with GitHub. Add New, then Project, then import the same repository.
2. **Root Directory: `frontend`**. Framework: Vite (detected automatically).
3. Environment variables:

| Name | Value |
|---|---|
| `VITE_API_URL` | `https://YOUR-SERVICE.onrender.com` (no slash at the end) |
| `VITE_PUBLIC_DEMO` | `1` |

4. Deploy. Vercel gives you an address like `https://your-project.vercel.app`.
5. **Go back to Render** and add one more variable, then save (it restarts):

| Name | Value |
|---|---|
| `ALLOWED_ORIGINS` | `https://your-project.vercel.app` |

6. Open the Vercel address. The header should say **Backend connected**. Click "Try the sample sales data" and ask a question.

## If something is wrong

| What you see | Likely cause and fix |
|---|---|
| Header says "Backend offline" on Vercel | `VITE_API_URL` is wrong, or `ALLOWED_ORIGINS` is missing the exact Vercel address. Fix it, then redeploy (Vercel) or save (Render) |
| First visit is very slow | Free servers usually go to sleep when idle and need a minute to wake. Open the app before presenting |
| "Too many questions" message | The rate limit is working. Raise `RATE_LIMIT_ANALYZE_PER_HOUR` if you need more |
| "daily question limit" message | The daily total is used up. Raise `GLOBAL_ANALYZE_PER_DAY` or wait |
| Answers fail with an AI error | Check `GROQ_API_KEY` and `LLM_MODEL` in the Render dashboard, and the provider's rate limits |
| Old datasets or history vanished | Free hosting usually wipes the disk when the service restarts. This is expected for a demo |

## Honest limits of this setup

- History and uploads may disappear on restart. Paid disks or a hosted database would fix that.
- Free hosting limits (sleeping, memory, hours) change over time, so check the provider's current terms.
- Per-visitor limits can be bypassed by a determined person, which is why the daily total exists as a backstop.
- Do not upload private data to the public demo. Files stay on the server.
- Watch your AI provider's usage page after you share the link.
