import { useEffect, useState } from "react";
import {
  getGmailStatus,
  getGmailLoginUrl,
  disconnectGmail,
  testFetchGmailMessages,
  processLatestGmailMessages,
  listEmailJobOrderDrafts,
  getEmailJobOrderDraft,
  saveEmailJobOrderDraft,
  dismissEmailJobOrderDraft,
  classifyWeightedActivity,
} from "../api";
import { Icon, Notice, Empty } from "../components/UI";
import RecordForm, { cleanFields } from "../components/RecordForm";
export default function Integrations({ capabilities, candidates, reload }) {
  const enabled = capabilities?.gmail_enabled;
  const [status, setStatus] = useState(null),
    [drafts, setDrafts] = useState([]),
    [draft, setDraft] = useState(null),
    [fields, setFields] = useState({});
  const [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [candidate, setCandidate] = useState(""),
    [activity, setActivity] = useState(null);
  async function refresh() {
    if (!enabled) return;
    const [s, d] = await Promise.all([
      getGmailStatus(),
      listEmailJobOrderDrafts({ status: "pending_review" }),
    ]);
    setStatus(s);
    setDrafts(d.drafts);
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, [enabled]);
  async function action(fn) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {error && <Notice type="error">{error}</Notice>}
      {message && <Notice>{message}</Notice>}
      <div className="integration-grid">
        <section className="panel integration-card">
          <span className="stat-icon blue">
            <Icon name="spark" size={26} />
          </span>
          <span className="tag integration-state">
            {capabilities?.ai_mode === "gemini" ? "Configured" : "Sample mode"}
          </span>
          <h2>Gemini document intelligence</h2>
          <p>
            Structured extraction, document vision, and semantic embeddings through a single AI
            boundary.
          </p>
          <dl>
            <div>
              <dt>Active mode</dt>
              <dd>{capabilities?.ai_mode === "gemini" ? "Gemini" : "Keyless sample"}</dd>
            </div>
            <div>
              <dt>Indexed candidates</dt>
              <dd>{capabilities?.indexed_candidates || 0}</dd>
            </div>
            <div>
              <dt>Document vision</dt>
              <dd>{capabilities?.vision_available ? "Configured" : "Requires Gemini"}</dd>
            </div>
          </dl>
          <details>
            <summary>Enable live AI locally</summary>
            <p>
              Set <code>AI_MODE=gemini</code> and <code>GEMINI_API_KEY</code> in the root
              environment file, restart the backend, then run the documented reindex command. Keep
              the key on the server.
            </p>
            <p>
              Use a free-tier Google AI Studio project. Quotas and data-use terms apply; there is no
              paid-provider fallback.
            </p>
          </details>
        </section>
        <section className="panel integration-card">
          <span className="stat-icon orange">
            <Icon name="mail" size={26} />
          </span>
          <span className="tag integration-state">
            {enabled ? (status?.authorized ? "Connected" : "Not connected") : "Optional · disabled"}
          </span>
          <h2>Gmail job order intake</h2>
          <p>
            Turn recruiter emails into reviewable drafts. Inspect extracted fields and deduplication
            before saving.
          </p>
          {!enabled ? (
            <Notice>
              Gmail is off by default. To opt in, enable it and provide your own OAuth client
              configuration. See the setup guide.
            </Notice>
          ) : (
            <>
              <p>{status?.email || "Connect an account to review incoming job orders."}</p>
              <div className="button-row">
                <a className="button secondary" href={getGmailLoginUrl()}>
                  Connect Gmail
                </a>
                <button
                  className="button secondary"
                  disabled={busy || !status?.authorized}
                  onClick={() =>
                    action(async () => {
                      await disconnectGmail();
                      await refresh();
                    })
                  }
                >
                  Disconnect
                </button>
              </div>
              <div className="button-row">
                <button
                  className="button secondary compact"
                  disabled={busy || !status?.authorized}
                  onClick={() =>
                    action(async () => {
                      const r = await testFetchGmailMessages();
                      setMessage(`${r.total_messages} messages found.`);
                    })
                  }
                >
                  Test fetch
                </button>
                <button
                  className="button primary compact"
                  disabled={busy || !status?.authorized}
                  onClick={() =>
                    action(async () => {
                      const r = await processLatestGmailMessages();
                      setMessage(`${r.created} drafts created; ${r.failed} failed.`);
                      await refresh();
                    })
                  }
                >
                  Process latest
                </button>
              </div>
            </>
          )}
        </section>
      </div>
      {enabled && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Review queue</h2>
              <p>Only reviewed email drafts become saved job orders.</p>
            </div>
            <button className="text-button" disabled={busy} onClick={() => action(refresh)}>
              Refresh drafts
            </button>
          </div>
          {!drafts.length && (
            <Empty title="No pending drafts">Process messages after connecting Gmail.</Empty>
          )}
          {drafts.map((d) => (
            <button
              className="draft-row"
              key={d.id}
              disabled={busy}
              onClick={() =>
                action(async () => {
                  const next = await getEmailJobOrderDraft(d.id);
                  setDraft(next);
                  setFields(next.extracted_fields);
                })
              }
            >
              <Icon name="mail" />
              <div>
                <strong>{d.subject || "Untitled email"}</strong>
                <small>
                  {d.sender} · {d.dedupe?.is_duplicate ? "Possible duplicate" : "Review required"}
                </small>
              </div>
              <Icon name="arrow" />
            </button>
          ))}
          {draft && (
            <div className="email-review">
              <h3>{draft.subject}</h3>
              <Notice>
                {draft.dedupe?.is_duplicate
                  ? "Possible duplicate: " + draft.dedupe.reasons.join("; ")
                  : "No duplicate detected."}{" "}
                Extraction: {draft.extraction_method.replaceAll("_", " ")}.
              </Notice>
              <details>
                <summary>Email source & attachments</summary>
                <p>{draft.sender}</p>
                {draft.attachments.map((a, i) => (
                  <p key={i}>{a.file_name}</p>
                ))}
                <pre className="document-preview">{draft.raw_text || draft.cleaned_body_text}</pre>
              </details>
              <RecordForm kind="job" value={fields} onChange={setFields} />
              <div className="button-row">
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      await saveEmailJobOrderDraft(draft.id, {
                        extracted_fields: cleanFields(fields),
                      });
                      setDraft(null);
                      await refresh();
                      await reload(true);
                      setMessage("Job order saved from reviewed draft.");
                    })
                  }
                >
                  Save reviewed job order
                </button>
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      await dismissEmailJobOrderDraft(draft.id);
                      setDraft(null);
                      await refresh();
                    })
                  }
                >
                  Dismiss draft
                </button>
              </div>
            </div>
          )}
        </section>
      )}
      <section className="panel experimental">
        <details>
          <summary>
            <Icon name="chart" size={18} /> Experimental activity lab{" "}
            <span className="tag">Synthetic signals</span>
          </summary>
          <p>
            This inherited clustering experiment uses generated visits, applications, and login
            activity. It does not measure real applicant engagement and does not contribute to match
            ranking.
          </p>
          <div className="button-row">
            <label className="field">
              <span>Candidate for experiment</span>
              <select
                aria-label="Candidate for experiment"
                value={candidate}
                onChange={(e) => {
                  setCandidate(e.target.value);
                  setActivity(null);
                }}
              >
                <option value="">Choose a candidate</option>
                {candidates.map((c) => (
                  <option key={c.id} value={c.candidate_id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="button secondary"
              disabled={!candidate || busy}
              onClick={() =>
                action(async () => setActivity(await classifyWeightedActivity(candidate)))
              }
            >
              Run experiment
            </button>
          </div>
          {activity && (
            <Notice>
              Synthetic activity label: {activity.activity_label}. Weighted score:{" "}
              {activity.activity_score.toFixed(2)}. Cluster: {activity.cluster}.
            </Notice>
          )}
        </details>
      </section>
    </>
  );
}
