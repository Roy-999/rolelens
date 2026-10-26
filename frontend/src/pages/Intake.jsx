import { useEffect, useRef, useState } from "react";
import { extractCandidate, extractJobOrder, submitCandidate, submitJobOrder } from "../api";
import RecordForm, { submission } from "../components/RecordForm";
import { Icon, Notice } from "../components/UI";

export default function Intake({ kind, sample, onSaved, onFinish }) {
  const job = kind === "job",
    sampleStarted = useRef(false);
  const [queue, setQueue] = useState([]),
    [index, setIndex] = useState(0),
    [review, setReview] = useState(null),
    [fields, setFields] = useState({});
  const [paste, setPaste] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(0),
    [finished, setFinished] = useState(false);
  async function extract(file, text) {
    setBusy(true);
    setError("");
    setReview(null);
    try {
      const result = job
        ? await extractJobOrder({ file, jobOrder: text })
        : await extractCandidate(file);
      setReview(result);
      setFields(result.extracted_fields);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function loadSample() {
    try {
      const response = await fetch(`/samples/${job ? "job-order" : "resume"}.txt`);
      if (!response.ok) throw new Error("Sample document unavailable.");
      const file = new File(
        [await response.text()],
        job ? "sample-job.txt" : "quinn-taylor-resume.txt",
        { type: "text/plain" },
      );
      setQueue([file]);
      setIndex(0);
      setFinished(false);
      await extract(file);
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    if (sample && !sampleStarted.current) {
      sampleStarted.current = true;
      loadSample();
    }
  }, []);
  function choose(files) {
    const next = Array.from(files).filter((f) => /\.(pdf|docx|txt|png|jpe?g|webp)$/i.test(f.name));
    if (!next.length) {
      setError("Choose a supported document type.");
      return;
    }
    setQueue(next);
    setIndex(0);
    setSaved(0);
    setFinished(false);
    extract(next[0]);
  }
  async function next() {
    if (index + 1 < queue.length) {
      setIndex(index + 1);
      await extract(queue[index + 1]);
    } else {
      setReview(null);
      setFinished(true);
    }
  }
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await (job ? submitJobOrder : submitCandidate)(submission(review, fields));
      setSaved((n) => n + 1);
      await onSaved(true);
      await next();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="intake-steps">
        <span className={!review && !finished ? "current" : ""}>
          01 <strong>Import document</strong>
        </span>
        <i />
        <span className={review ? "current" : ""}>
          02 <strong>Review & refine</strong>
        </span>
        <i />
        <span className={finished ? "current" : ""}>
          03 <strong>Save to workspace</strong>
        </span>
      </div>
      {error && (
        <Notice type="error">
          {error}{" "}
          {queue.length > 1 && (
            <button className="text-button" disabled={busy} onClick={next}>
              Skip this file
            </button>
          )}
        </Notice>
      )}
      {finished ? (
        <section className="panel success-panel">
          <span className="success-icon">
            <Icon name="check" size={28} />
          </span>
          <p className="eyebrow">WORKSPACE UPDATED</p>
          <h2>
            {saved} {job ? "job order" : "candidate"}
            {saved !== 1 ? "s" : ""} saved
          </h2>
          <p>Your reviewed records are ready to explore.</p>
          <button className="button primary" onClick={onFinish}>
            View {job ? "job orders" : "candidates"} <Icon name="arrow" size={17} />
          </button>
          <button
            className="text-button"
            onClick={() => {
              setFinished(false);
              setQueue([]);
              setSaved(0);
            }}
          >
            Import more documents
          </button>
        </section>
      ) : review ? (
        <div className="review-layout">
          <aside className="panel source-panel">
            <p className="eyebrow">SOURCE DOCUMENT</p>
            <h2>{review.file_name}</h2>
            <span className="tag">{review.extraction_method.replaceAll("_", " ")}</span>
            {queue.length > 1 && (
              <Notice>
                Document {index + 1} of {queue.length} · {saved} saved. Each record is reviewed
                before saving.
              </Notice>
            )}
            <pre className="document-preview">
              {review.raw_text || review.preview_text || "Image document; review extracted fields."}
            </pre>
            <p className="help-text">
              Compare the extracted fields with the original. Missing information stays empty.
            </p>
          </aside>
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>Review extracted details</h2>
                <p>Make it accurate before it enters your workspace.</p>
              </div>
              <span className="tag blue-tag">Human review</span>
            </div>
            {review.extraction_method === "demo_heuristic" && (
              <Notice>
                Sample mode uses text patterns, with limited extraction accuracy. Review every
                field.
              </Notice>
            )}
            {review.warnings.map((w) => (
              <Notice key={w}>{w}</Notice>
            ))}
            <form onSubmit={save}>
              <RecordForm kind={kind} value={fields} onChange={setFields} />
              <div className="sticky-actions">
                <button type="button" className="button secondary" disabled={busy} onClick={next}>
                  {queue.length > 1 ? "Skip document" : "Discard"}
                </button>
                <button className="button primary" disabled={busy}>
                  {busy
                    ? "Saving…"
                    : queue.length > 1 && index + 1 < queue.length
                      ? "Save & review next"
                      : `Save ${job ? "job order" : "candidate"}`}
                  <Icon name="check" size={17} />
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : (
        <div className="intake-layout">
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>{job ? "Import a job order" : "Import candidate documents"}</h2>
                <p>Start with a single file or review a batch, one document at a time.</p>
              </div>
              <Icon name="upload" />
            </div>
            <label className={`dropzone ${busy ? "disabled" : ""}`}>
              <span className="upload-symbol">
                <Icon name="upload" size={26} />
              </span>
              <strong>{busy ? "Reading your document…" : "Choose documents to get started"}</strong>
              <span>PDF, DOCX, TXT, PNG, JPEG, or WEBP · up to 10 MB each</span>
              <span className="button primary">{busy ? "Extracting…" : "Browse files"}</span>
              <input
                type="file"
                aria-label="Upload documents"
                accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp"
                multiple
                disabled={busy}
                onChange={(e) => choose(e.target.files)}
              />
            </label>
            <div className="import-secondary">
              <label className="button secondary compact">
                Choose folder
                <input
                  aria-label="Upload folder"
                  type="file"
                  webkitdirectory=""
                  multiple
                  hidden
                  disabled={busy}
                  onChange={(e) => choose(e.target.files)}
                />
              </label>
              <a href={`/samples/${job ? "job-order" : "resume"}.txt`} download>
                Download sample document ↗
              </a>
            </div>
            {job && (
              <div className="paste-section">
                <p className="eyebrow">OR START WITH TEXT</p>
                <label className="field">
                  <span>Job description</span>
                  <textarea
                    rows={8}
                    value={paste}
                    onChange={(e) => setPaste(e.target.value)}
                    placeholder="Paste the role, requirements, and responsibilities…"
                  />
                </label>
                <button
                  className="button primary"
                  disabled={busy || !paste.trim()}
                  onClick={() => {
                    setQueue([]);
                    extract(null, paste);
                  }}
                >
                  Extract job details <Icon name="arrow" size={16} />
                </button>
              </div>
            )}
          </section>
          <aside className="panel sample-panel">
            <span className="stat-icon blue">
              <Icon name="spark" size={24} />
            </span>
            <p className="eyebrow">TAKE IT FOR A SPIN</p>
            <h2>
              A small sample.
              <br />
              The complete workflow.
            </h2>
            <p>
              Explore intake with a fictional {job ? "job description" : "resume"}. Inspect the
              source, correct the details, and save the result.
            </p>
            <button className="button secondary" disabled={busy} onClick={loadSample}>
              Use sample {job ? "job order" : "resume"}
              <Icon name="arrow" size={16} />
            </button>
            <div className="sample-note">
              <Icon name="file" size={16} />
              <span>
                Invented people and organizations.
                <br />
                No real applicant information.
              </span>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
