# Frontend (React + Vite)

The web interface for the Agentic Data Analyst: upload a CSV/Excel file, ask a question, read the
answer with every number checked, see the charts and the calculations behind the answer, and
download the report.

## Run it (one server, simplest)

```powershell
cd frontend
npm install
npm run build          # creates frontend/dist
cd ..\backend
uvicorn app.main:app   # serves the API and the built UI together
```

Open http://127.0.0.1:8000

## Run it for development (two terminals, live reload)

Terminal 1 (backend): `cd backend` then `uvicorn app.main:app --reload`
Terminal 2 (frontend): `cd frontend` then `npm run dev`, and open http://localhost:5173

## Tests

`npm test` (28 tests: number highlighting, display formatting, run summary and screen rendering)

## Notes
- `VITE_API_URL` overrides the backend address (default `http://127.0.0.1:8000` in dev, same address when built).
- Fonts load from Google Fonts; without internet the app falls back to system fonts.
