import { BrandMark, Moon, Sun } from "./Icons.jsx";

export default function Header({ theme, onToggleTheme, online }) {
  const label = online === null ? "Checking backend" : online ? "Backend connected" : "Backend offline";
  return (
    <header className="band">
      <div className="band__inner">
        <div className="brand">
          <BrandMark />
          <div>
            <h1 className="brand__name">Agentic Data Analyst</h1>
            <p className="brand__tag">Ask your spreadsheet a question. Every number in the answer is checked.</p>
          </div>
        </div>
        <div className="band__tools">
          <span className={`status ${online === false ? "status--off" : online ? "status--on" : ""}`} role="status">
            <span className="status__dot" aria-hidden="true" />
            {label}
          </span>
          <button
            type="button"
            className="iconbtn"
            onClick={onToggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            title={theme === "dark" ? "Light mode" : "Dark mode"}
          >
            {theme === "dark" ? <Sun /> : <Moon />}
          </button>
        </div>
      </div>
    </header>
  );
}
