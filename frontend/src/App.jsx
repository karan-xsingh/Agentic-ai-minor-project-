import { useCallback, useEffect, useMemo, useState } from "react";
import { analyze, getAnalysis, getDataset, getProfile, health, listAnalyses, uploadDataset } from "./api.js";
import Answer from "./components/Answer.jsx";
import AskBar from "./components/AskBar.jsx";
import Header from "./components/Header.jsx";
import History from "./components/History.jsx";
import Overview from "./components/Overview.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import Welcome from "./components/Welcome.jsx";
import { suggestQuestions } from "./lib/report.js";

const PUBLIC_NOTICE = import.meta.env.VITE_PUBLIC_DEMO === "1"
  ? "Public demo: files are kept on the server. Please do not upload private or sensitive data."
  : "";
const STORE_KEY = "analyst.datasetId";
const remember = (id) => { try { id ? localStorage.setItem(STORE_KEY, id) : localStorage.removeItem(STORE_KEY); } catch { /* storage unavailable */ } };
const recall = () => { try { return localStorage.getItem(STORE_KEY); } catch { return null; } };

export default function App() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "light");
  const [online, setOnline] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [profile, setProfile] = useState(null);
  const [history, setHistory] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [activeEvidence, setActiveEvidence] = useState(null);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;   // set first so charts read the new colours
    try { localStorage.setItem("analyst.theme", next); } catch { /* storage unavailable */ }
    setTheme(next);
  };

  const refreshHistory = useCallback((id) => listAnalyses(id).then(setHistory).catch(() => {}), []);
  const loadProfile = useCallback((id) => getProfile(id).then(setProfile).catch(() => setProfile(null)), []);

  useEffect(() => {
    const check = () => health().then(() => setOnline(true)).catch(() => setOnline(false));
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, []);

  // Pick up where the person left off after a page refresh.
  useEffect(() => {
    const id = recall();
    if (!id) return;
    getDataset(id)
      .then((ds) => { setDataset(ds); refreshHistory(id); loadProfile(id); })
      .catch((e) => { if (e.status === 404) remember(null); });
  }, [refreshHistory, loadProfile]);

  useEffect(() => {
    if (!busy) return undefined;
    setElapsed(0);
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [busy]);

  const onUpload = async (file) => {
    setUploading(true);
    setUploadError("");
    try {
      const ds = await uploadDataset(file);
      setDataset(ds);
      setProfile(null);
      setHistory([]);
      setAnalysis(null);
      setError("");
      setQuestion("");
      remember(ds.dataset_id);
      loadProfile(ds.dataset_id);
    } catch (e) {
      setUploadError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const onSample = async () => {
    setUploading(true);
    setUploadError("");
    try {
      const res = await fetch(`${import.meta.env.BASE_URL}sales.csv`);
      if (!res.ok) throw new Error("The sample file could not be loaded.");
      await onUpload(new File([await res.blob()], "sales.csv", { type: "text/csv" }));
    } catch (e) {
      setUploadError(e.message);
      setUploading(false);
    }
  };

  const onAsk = async (q) => {
    setBusy(true);
    setError("");
    setActiveEvidence(null);
    try {
      setAnalysis(await analyze(dataset.dataset_id, q));
      refreshHistory(dataset.dataset_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const openPast = async (id) => {
    setError("");
    setActiveEvidence(null);
    try {
      const a = await getAnalysis(id);
      setAnalysis(a);
      setQuestion(a.question);
    } catch (e) {
      setError(e.message);
    }
  };

  const suggestions = useMemo(() => (dataset ? suggestQuestions(dataset.columns) : []), [dataset]);

  return (
    <>
      <Header theme={theme} onToggleTheme={toggleTheme} online={online} />
      <div className="shell">
        <div className="workbench">
          <aside className="rail">
            <UploadPanel dataset={dataset} uploading={uploading} error={uploadError} onUpload={onUpload} notice={PUBLIC_NOTICE} />
            <History items={history} selectedId={analysis?.analysis_id} onSelect={openPast} />
          </aside>

          <main className="main">
            {!dataset ? (
              <Welcome onSample={onSample} busy={uploading} />
            ) : (
              <>
                <AskBar question={question} setQuestion={setQuestion} onAsk={onAsk} busy={busy} suggestions={analysis ? [] : suggestions} />

                {error && <p className="notice notice--error" role="alert">{error}</p>}

                {busy && (
                  <p className="working" role="status">
                    Analyzing your question ({elapsed}s). This usually takes 5 to 20 seconds.
                    <span className="working__bar" aria-hidden="true" />
                  </p>
                )}

                {analysis && !busy && (
                  <Answer analysis={analysis} activeEvidence={activeEvidence} onSelectEvidence={(id) => setActiveEvidence({ id, tick: Date.now() })} theme={theme} />
                )}

                <Overview profile={profile} open={!analysis} />
              </>
            )}
          </main>
        </div>
      </div>
    </>
  );
}
