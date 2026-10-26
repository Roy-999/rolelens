import { useEffect, useState } from "react";
import { listCandidates, listJobOrders, getCapabilities } from "./api";
import { Icon, Brand, Notice } from "./components/UI";
import Overview from "./pages/Overview";
import Records from "./pages/Records";
import Intake from "./pages/Intake";
import Matching from "./pages/Matching";
import Integrations from "./pages/Integrations";

const NAV = [
  ["overview", "grid", "Overview"],
  ["candidates", "people", "Candidates"],
  ["jobs", "briefcase", "Job orders"],
  ["matching", "spark", "Matching studio"],
  ["integrations", "plug", "Integrations"],
];
const TITLES = {
  overview: "Workspace overview",
  candidates: "Your talent, organized",
  jobs: "Every role, in focus",
  matching: "Find the relevant people",
  integrations: "Connect your workflow",
  intake: "From document to structured data",
};
export default function App() {
  const [page, setPage] = useState("overview"),
    [candidates, setCandidates] = useState([]),
    [jobs, setJobs] = useState([]);
  const [capabilities, setCapabilities] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [intake, setIntake] = useState({ kind: "candidate", sample: false }),
    [selectedJob, setSelectedJob] = useState(null);
  async function reload(background = false) {
    if (!background) setLoading(true);
    setError("");
    try {
      const [people, roles, caps] = await Promise.all([
        listCandidates(),
        listJobOrders(),
        getCapabilities(),
      ]);
      setCandidates(people.candidates);
      setJobs(roles.jobs);
      setCapabilities(caps);
    } catch (e) {
      setError(e.message);
    } finally {
      if (!background) setLoading(false);
    }
  }
  useEffect(() => {
    reload();
  }, []);
  function navigate(next) {
    setPage(next);
    window.scrollTo({ top: 0 });
  }
  function startIntake(kind, sample = false) {
    setIntake({ kind, sample, key: Date.now() });
    navigate("intake");
  }
  function startMatch(job) {
    setSelectedJob(job || null);
    navigate("matching");
  }
  const demo = capabilities?.ai_mode !== "gemini";
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="sidebar">
        <Brand />
        <div className="workspace-label">
          <span className="workspace-monogram">R</span>
          <div>
            Recruiting workspace<small>Portfolio edition</small>
          </div>
          <Icon name="chevrons" size={14} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {NAV.map(([id, icon, label]) => (
            <button
              key={id}
              aria-label={label}
              title={label}
              className={`nav-item ${page === id ? "active" : ""}`}
              onClick={() => navigate(id)}
              aria-current={page === id ? "page" : undefined}
            >
              <Icon name={icon} />
              <span>{label}</span>
              {id === "matching" && <span className="nav-new">AI</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="status-dot" /> BUILT TO EXPLORE
            <h3>
              A working idea.
              <br />
              An open workbench.
            </h3>
            <p>Document intelligence meets thoughtful recruiting.</p>
            <a href="/api/docs" target="_blank" rel="noreferrer">
              Explore the API <Icon name="arrow" size={14} />
            </a>
          </div>
          <div className="sidebar-footer">
            <span className="avatar small">SR</span>
            <div>
              Swapnil Roy<small>Applied AI & engineering</small>
            </div>
            <span className="version">v0.1</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span>{" "}
            <strong>{NAV.find((n) => n[0] === page)?.[2] || "Document intake"}</strong>
          </div>
          <div className="topbar-right">
            <span className={`mode-badge ${demo ? "" : "live"}`}>
              <span className="status-dot" />
              {capabilities ? (demo ? "Sample mode" : "Gemini enabled") : "Connecting"}
            </span>
            <a
              className="icon-button"
              href="/api/docs"
              aria-label="API documentation"
              target="_blank"
              rel="noreferrer"
            >
              <Icon name="code" />
            </a>
            <span className="avatar">SR</span>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          <div className="page-heading">
            <div>
              <p className="eyebrow">ROLELENS / RECRUITING INTELLIGENCE</p>
              <h1>{TITLES[page]}</h1>
              <p className="page-subtitle">
                {page === "overview"
                  ? "Less time organizing documents. More time understanding people."
                  : page === "matching"
                    ? "Explore the evidence behind every candidate recommendation."
                    : "A clearer view of the information that matters."}
              </p>
            </div>
            {["overview", "candidates", "jobs"].includes(page) && (
              <button
                className="button primary"
                onClick={() => startIntake(page === "jobs" ? "job" : "candidate")}
              >
                <Icon name="plus" size={17} />
                {page === "jobs" ? "Add job order" : "Add candidate"}
              </button>
            )}
          </div>
          {error && (
            <Notice type="error">
              <strong>Workspace unavailable.</strong> {error}{" "}
              <button className="text-button" onClick={reload}>
                Retry connection
              </button>
            </Notice>
          )}
          {loading ? (
            <div className="loading-card" role="status">
              <span className="spinner" /> Loading workspace…
            </div>
          ) : (
            <>
              {page === "overview" && (
                <Overview
                  candidates={candidates}
                  jobs={jobs}
                  demo={demo}
                  navigate={navigate}
                  startIntake={startIntake}
                  startMatch={startMatch}
                />
              )}
              {page === "candidates" && (
                <Records
                  kind="candidate"
                  records={candidates}
                  reload={reload}
                  startIntake={startIntake}
                />
              )}
              {page === "jobs" && (
                <Records
                  kind="job"
                  records={jobs}
                  reload={reload}
                  startIntake={startIntake}
                  startMatch={startMatch}
                />
              )}
              {page === "intake" && (
                <Intake
                  key={intake.key}
                  kind={intake.kind}
                  sample={intake.sample}
                  onSaved={reload}
                  onFinish={() => navigate(intake.kind === "candidate" ? "candidates" : "jobs")}
                />
              )}
              {page === "matching" && (
                <Matching
                  jobs={jobs}
                  candidates={candidates}
                  initialJob={selectedJob}
                  demo={demo}
                />
              )}
              {page === "integrations" && (
                <Integrations capabilities={capabilities} candidates={candidates} reload={reload} />
              )}
            </>
          )}
          <footer className="page-footer">
            <span>
              <span className="mini-mark">◈</span> RoleLens{" "}
              <span className="muted">/ AI recruiting workbench</span>
            </span>
            <span>
              {capabilities?.sample_data
                ? "Fictional sample dataset · Human review required"
                : "Portfolio POC · Human review required"}
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
