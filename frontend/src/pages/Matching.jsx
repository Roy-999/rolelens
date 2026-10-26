import { useState } from "react";
import { matchJob, extractSalary } from "../api";
import { Empty, Icon, Notice, Tags, initials, location } from "../components/UI";
export default function Matching({ jobs, candidates, initialJob, demo }) {
  const [jobId, setJobId] = useState(initialJob?.id || ""),
    [text, setText] = useState(initialJob?.raw_text || ""),
    [file, setFile] = useState(null);
  const [limit, setLimit] = useState(5),
    [city, setCity] = useState(""),
    [result, setResult] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [salary, setSalary] = useState("");
  const selected = jobs.find((j) => j.id === jobId);
  function choose(id) {
    setJobId(id);
    setText(jobs.find((j) => j.id === id)?.raw_text || "");
    setFile(null);
    setResult(null);
    setSalary("");
  }
  async function run(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await matchJob({ file, jobOrder: text, limit, city }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function salaryCheck() {
    setBusy(true);
    setError("");
    try {
      setSalary((await extractSalary({ file, jobOrder: text })).salary_range);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="studio-banner">
        <Icon name="spark" />
        <span>
          {demo
            ? "Keyword matching is active. Enable Gemini and index profiles to add semantic retrieval."
            : "Gemini is enabled. Semantic retrieval uses compatible indexed profiles; keyword fallback is clearly labeled."}
        </span>
        <span className="tag">Evidence first</span>
      </div>
      <div className="studio-layout">
        <section className="panel studio-input">
          <div className="section-heading">
            <div>
              <p className="eyebrow">01 / THE OPPORTUNITY</p>
              <h2>Start with a role</h2>
            </div>
            <Icon name="briefcase" />
          </div>
          <form onSubmit={run}>
            <label className="field">
              <span>Saved job order</span>
              <select
                aria-label="Saved job order"
                value={jobId}
                onChange={(e) => choose(e.target.value)}
              >
                <option value="">Choose a role or paste text below</option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.job_title} · {j.organization_name}
                  </option>
                ))}
              </select>
            </label>
            {selected && (
              <div className="selected-job">
                <strong>{selected.job_title}</strong>
                <p>{selected.organization_name}</p>
                <span className="job-meta">
                  <Icon name="pin" size={14} />
                  {location(selected)}
                </span>
                <Tags items={selected.skills} />
              </div>
            )}
            <label className="field">
              <span>Job description</span>
              <textarea
                aria-label="Job description"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={9}
                placeholder="Describe the skills and experience you need…"
              />
            </label>
            <label className="field">
              <span>Or upload a job document</span>
              <input
                type="file"
                accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp"
                onChange={(e) => {
                  setFile(e.target.files[0] || null);
                  setResult(null);
                }}
              />
            </label>
            <div className="form-grid">
              <label className="field">
                <span>Candidate location</span>
                <select
                  aria-label="Candidate location"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                >
                  <option value="">All locations</option>
                  {[...new Set(candidates.map((c) => c.location.city).filter(Boolean))]
                    .sort()
                    .map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                </select>
              </label>
              <label className="field">
                <span>Maximum results</span>
                <select
                  aria-label="Maximum results"
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value))}
                >
                  {[3, 5, 10].map((n) => (
                    <option key={n} value={n}>
                      {n} candidates
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button
              className="button primary full-width"
              disabled={busy || (!text.trim() && !file)}
            >
              {busy ? "Analyzing evidence…" : "Find matching candidates"}
              <Icon name="spark" size={17} />
            </button>
            <button
              type="button"
              className="text-button salary-button"
              disabled={busy || (!text.trim() && !file)}
              onClick={salaryCheck}
            >
              Inspect compensation <Icon name="arrow" size={15} />
            </button>
            {salary && <Notice>{salary}</Notice>}
          </form>
        </section>
        <section className="studio-results">
          <div className="section-heading">
            <div>
              <p className="eyebrow">02 / THE EVIDENCE</p>
              <h2>
                {result ? `${result.candidates.length} relevant candidates` : "A clearer shortlist"}
              </h2>
              <p>
                {result
                  ? `${result.available_candidates} profiles considered · ${result.matching_mode === "hybrid" ? "Keyword + semantic fusion" : "Keyword evidence"}`
                  : "The right context makes a better conversation."}
              </p>
            </div>
            {result && (
              <span className="tag blue-tag">
                {result.matching_mode === "hybrid" ? "Hybrid" : "Keyword only"}
              </span>
            )}
          </div>
          {error && <Notice type="error">{error}</Notice>}
          {result?.warnings.map((w) => (
            <Notice key={w}>{w}</Notice>
          ))}
          {busy && (
            <div className="loading-card" role="status">
              <span className="spinner" /> Comparing candidate evidence…
            </div>
          )}
          {!busy && !result && (
            <div className="matching-empty">
              <div className="match-orbits">
                <span>
                  <Icon name="people" size={34} />
                </span>
              </div>
              <h3>Good matches start with context.</h3>
              <p>
                Choose a job order and explore the skills,
                <br />
                experience, and evidence behind the ranking.
              </p>
              <div className="evidence-pills">
                <span>Skill overlap</span>
                <span>Semantic similarity*</span>
                <span>Location</span>
              </div>
              <small>*When Gemini embeddings are available.</small>
            </div>
          )}
          {!busy && result && !result.candidates.length && (
            <Empty title="No relevant evidence found">
              Try broadening the role description or location filter.
            </Empty>
          )}
          {!busy &&
            result?.candidates.map((c, i) => (
              <article className="panel match-card" key={c.resume_id}>
                <div className="match-card-top">
                  <div className="person">
                    <span className={`avatar person-avatar tone-${i % 4}`}>{initials(c.name)}</span>
                    <div>
                      <h3>{c.name}</h3>
                      <p>{c.experience?.[0]?.title || "Candidate profile"}</p>
                    </div>
                  </div>
                  <span className="rank-badge">
                    #{i + 1} <span>RANK</span>
                  </span>
                </div>
                <div className="match-meta">
                  <span>
                    <Icon name="pin" size={14} />
                    {location(c)}
                  </span>
                  <span>
                    <Icon name="clock" size={14} />
                    {c.years_of_experience ?? "—"} years experience
                  </span>
                </div>
                <p className="match-summary">
                  {c.experience?.[0]?.summary ||
                    "Review the candidate profile for further context."}
                </p>
                <div className="match-evidence">
                  <span className="eyebrow">MATCHED TERMS</span>
                  <Tags items={c.matched_terms} max={12} />
                </div>
                <details>
                  <summary>Inspect ranking signals</summary>
                  <div className="signal-grid">
                    <div>
                      <small>Keyword overlap</small>
                      <strong>{(c.keyword_score * 100).toFixed(1)}%</strong>
                    </div>
                    <div>
                      <small>Cosine similarity</small>
                      <strong>
                        {c.source.includes("vector") ? c.vector_score.toFixed(3) : "Unavailable"}
                      </strong>
                    </div>
                    <div>
                      <small>Ranking score</small>
                      <strong>{c.rrf_score.toFixed(4)}</strong>
                    </div>
                  </div>
                  <p className="help-text">
                    Source: {c.source}. Keyword overlap measures shared terms. The ranking score
                    orders evidence; it is not a probability of job performance.
                  </p>
                </details>
              </article>
            ))}
        </section>
      </div>
    </>
  );
}
