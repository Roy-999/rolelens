import { useState } from "react";
import { updateCandidate, updateJobOrder } from "../api";
import { Empty, Icon, Notice, Tags, initials, location, role } from "../components/UI";
import RecordForm, { submission } from "../components/RecordForm";

export default function Records({ kind, records, reload, startIntake, startMatch }) {
  const job = kind === "job";
  const [search, setSearch] = useState(""),
    [city, setCity] = useState("");
  const [selected, setSelected] = useState(null),
    [editing, setEditing] = useState(false),
    [fields, setFields] = useState({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const filtered = records.filter(
    (r) =>
      JSON.stringify([r.name, r.job_title, r.organization_name, r.skills, r.experience])
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (!city || r.location?.city === city),
  );
  function open(record) {
    setSelected(record);
    setFields(structuredClone(record));
    setEditing(false);
    setError("");
  }
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await (job ? updateJobOrder : updateCandidate)(
        selected.job_order_id || selected.candidate_id || selected.id,
        submission(selected, fields),
      );
      setSelected(null);
      await reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (selected)
    return (
      <section className="panel detail-panel">
        <div className="section-heading">
          <div>
            <button className="text-button back-button" onClick={() => setSelected(null)}>
              ← Back to {job ? "job orders" : "candidates"}
            </button>
            <h2>{job ? selected.job_title : selected.name}</h2>
            <p>
              {job ? selected.organization_name : role(selected)} · {location(selected)}
            </p>
          </div>
          <div className="button-row">
            {job && (
              <button className="button primary" onClick={() => startMatch(selected)}>
                Find candidates <Icon name="arrow" size={16} />
              </button>
            )}
            <button
              className="button secondary"
              onClick={() => {
                setEditing(!editing);
                setFields(structuredClone(selected));
              }}
            >
              {editing ? "Cancel edit" : "Edit record"}
            </button>
          </div>
        </div>
        {error && <Notice type="error">{error}</Notice>}
        {editing ? (
          <form onSubmit={save}>
            <RecordForm kind={kind} value={fields} onChange={setFields} />
            <div className="sticky-actions">
              <button className="button primary" disabled={busy}>
                {busy ? "Saving…" : "Save changes"}
              </button>
            </div>
          </form>
        ) : (
          <>
            <div className="detail-summary">
              <span className="tag">{selected.extraction_method.replaceAll("_", " ")}</span>
              <span className="muted">{selected.candidate_id || selected.job_order_id}</span>
            </div>
            <h3>Core skills</h3>
            <Tags items={selected.skills} max={50} />
            {job ? (
              <>
                <h3>Role summary</h3>
                <p className="body-copy">{selected.summary || "No summary provided."}</p>
                <h3>Compensation</h3>
                <p>{selected.compensation?.pay_text || "Not specified"}</p>
                {["responsibilities", "qualifications", "benefits"].map((k) => (
                  <div key={k}>
                    <h3>{k[0].toUpperCase() + k.slice(1)}</h3>
                    <ul className="detail-list">
                      {selected[k].map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </>
            ) : (
              <>
                <div className="detail-facts">
                  <div>
                    <small>EMAIL</small>
                    <p>{selected.email_id || "Not provided"}</p>
                  </div>
                  <div>
                    <small>EXPERIENCE</small>
                    <p>{selected.years_of_experience ?? "—"} years</p>
                  </div>
                  <div>
                    <small>PROFILE COMPLETENESS</small>
                    <p>{selected.profile_completion_percentage}%</p>
                  </div>
                </div>
                <h3>Experience</h3>
                {selected.experience.map((entry, i) => (
                  <article className="experience-card" key={i}>
                    <strong>{entry.title || "Experience entry"}</strong>
                    <p>
                      {entry.company}{" "}
                      {entry.start_date && `· ${entry.start_date} – ${entry.end_date}`}
                    </p>
                    <p>{entry.summary}</p>
                  </article>
                ))}
                <h3>Credentials & tools</h3>
                <Tags
                  items={[...selected.tools, ...selected.certifications, ...selected.licenses]}
                  max={50}
                />
              </>
            )}
            <details>
              <summary>Source document</summary>
              <pre className="document-preview">
                {selected.raw_text || "Source text unavailable."}
              </pre>
            </details>
          </>
        )}
      </section>
    );
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2>
            {job ? "Job order library" : "Candidate library"}{" "}
            <span className="count">{records.length}</span>
          </h2>
          <p>
            {job
              ? "Requirements, context, and your next search."
              : "Search the experience and skills in your workspace."}
          </p>
        </div>
        <button className="button secondary compact" onClick={() => startIntake(kind)}>
          <Icon name="upload" size={16} />
          Bulk intake
        </button>
      </div>
      <div className="filter-bar">
        <label className="search-field">
          <Icon name="search" size={18} />
          <input
            aria-label={`Search ${job ? "job orders" : "candidates"}`}
            placeholder={
              job ? "Search titles, companies, or skills…" : "Search names, roles, or skills…"
            }
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select aria-label="Filter by city" value={city} onChange={(e) => setCity(e.target.value)}>
          <option value="">All locations</option>
          {[...new Set(records.map((r) => r.location?.city).filter(Boolean))].sort().map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <span className="muted">{filtered.length} results</span>
      </div>
      {!filtered.length ? (
        <Empty title="No records found">Try a different search or add a document.</Empty>
      ) : job ? (
        <div className="record-job-grid">
          {filtered.map((r, i) => (
            <article className="job-record" key={r.id}>
              <div className="job-preview-top">
                <span className={`company-mark tone-${i % 4}`}>
                  {initials(r.organization_name || "Job")}
                </span>
                <span className="tag subtle">{r.domain || "Other"}</span>
              </div>
              <button className="record-title" onClick={() => open(r)}>
                {r.job_title || "Untitled role"}
              </button>
              <p className="muted">{r.organization_name || "Organization not provided"}</p>
              <p className="job-meta">
                <Icon name="pin" size={15} />
                {location(r)}
              </p>
              <Tags items={r.skills} max={4} />
              <div className="job-preview-bottom">
                <button className="text-button" onClick={() => open(r)}>
                  View details
                </button>
                <button className="text-button" onClick={() => startMatch(r)}>
                  Find candidates <Icon name="arrow" size={15} />
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>CANDIDATE</th>
                <th>CORE SKILLS</th>
                <th>LOCATION</th>
                <th>EXPERIENCE</th>
                <th>PROFILE</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr key={r.id}>
                  <td>
                    <div className="person">
                      <span className={`avatar person-avatar tone-${i % 4}`}>
                        {initials(r.name)}
                      </span>
                      <div>
                        <button className="record-title" onClick={() => open(r)}>
                          {r.name || "Unnamed candidate"}
                        </button>
                        <small>{role(r)}</small>
                      </div>
                    </div>
                  </td>
                  <td>
                    <Tags items={r.skills} max={3} />
                  </td>
                  <td>{r.location?.city || "—"}</td>
                  <td>{r.years_of_experience ?? "—"} years</td>
                  <td>
                    <span className="completion">
                      {r.profile_completion_percentage}%
                      <span style={{ width: `${r.profile_completion_percentage}%` }} />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
