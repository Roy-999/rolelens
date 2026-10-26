import { Icon, Tags, initials, location, role } from "../components/UI";
export default function Overview({ candidates, jobs, demo, navigate, startIntake, startMatch }) {
  const skillCount = new Set(candidates.flatMap((c) => c.skills.map((s) => s.toLowerCase()))).size;
  return (
    <>
      <section className="intro-banner">
        <div className="intro-content">
          <span className="banner-kicker">
            <span className="status-dot" /> YOUR NEXT GREAT MATCH STARTS HERE
          </span>
          <h2>
            See the person.
            <br />
            Find the possibility.
          </h2>
          <p>
            Turn resumes and job descriptions into structured profiles.
            <br className="desktop-break" /> Bring the right evidence into every recruiting
            conversation.
          </p>
          <div className="button-row">
            <button className="button white" onClick={() => startIntake("candidate", true)}>
              Try sample workflow <Icon name="arrow" size={17} />
            </button>
            <button
              className="button banner-link"
              onClick={() =>
                startMatch(jobs.find((j) => j.job_order_id === "RL-JOB-001") || jobs[0])
              }
            >
              Open matching studio <Icon name="arrow" size={16} />
            </button>
          </div>
          <span className="banner-footnote">
            {demo
              ? "No API key needed · Clearly labeled heuristic extraction"
              : "Gemini document extraction · Human review before saving"}
          </span>
        </div>
        <div className="lens-illustration" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit orbit-three" />
          <div className="lens-center">
            <Icon name="spark" size={40} />
          </div>
          <div className="floating-card top">
            <span className="floating-avatar">MC</span>
            <div>
              <strong>Structured profiles</strong>
              <small>Skills, experience, context</small>
            </div>
            <span className="tiny-check">✓</span>
          </div>
          <div className="floating-card bottom">
            <span className="floating-icon">
              <Icon name="briefcase" />
            </span>
            <div>
              <strong>Relevant connections</strong>
              <small>Evidence you can inspect</small>
            </div>
            <Icon name="arrow" size={16} />
          </div>
          <div className="orbit-dot dot-one" />
          <div className="orbit-dot dot-two" />
        </div>
      </section>
      <div className="stat-grid">
        {[
          [
            "people",
            candidates.length,
            "Candidate profiles",
            "Structured and ready to explore",
            "blue",
          ],
          ["briefcase", jobs.length, "Job orders", "Roles with context and requirements", "purple"],
          ["spark", skillCount, "Distinct skills", "Across your candidate workspace", "orange"],
        ].map(([icon, value, label, detail, tone]) => (
          <article className="stat-card" key={label}>
            <div className="stat-top">
              <span>{label}</span>
              <span className={`stat-icon ${tone}`}>
                <Icon name={icon} />
              </span>
            </div>
            <strong className="stat-value">{value.toString().padStart(2, "0")}</strong>
            <p>
              <span className="small-line" />
              {detail}
            </p>
          </article>
        ))}
      </div>
      <div className="overview-columns">
        <section className="panel recent-panel">
          <div className="section-heading">
            <div>
              <h2>People in your workspace</h2>
              <p>A quick look at the talent behind the documents.</p>
            </div>
            <button className="text-button" onClick={() => navigate("candidates")}>
              View all <Icon name="arrow" size={16} />
            </button>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>CANDIDATE</th>
                  <th>EXPERTISE</th>
                  <th>LOCATION</th>
                  <th aria-label="Open profile" />
                </tr>
              </thead>
              <tbody>
                {candidates
                  .slice()
                  .sort((a, b) => a.candidate_id.localeCompare(b.candidate_id))
                  .slice(0, 4)
                  .map((c, i) => (
                    <tr key={c.id}>
                      <td>
                        <div className="person">
                          <span className={`avatar person-avatar tone-${i % 4}`}>
                            {initials(c.name)}
                          </span>
                          <div>
                            <strong>{c.name}</strong>
                            <small>{role(c)}</small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <Tags items={c.skills} max={2} />
                      </td>
                      <td className="location-cell">{c.location.city || "—"}</td>
                      <td>
                        <button
                          className="icon-button"
                          onClick={() => navigate("candidates")}
                          aria-label={`Browse candidates including ${c.name}`}
                        >
                          <Icon name="arrow" size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="panel workflow-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">THE WORKFLOW</p>
              <h2>Three steps to clarity</h2>
            </div>
            <Icon name="spark" />
          </div>
          {[
            [
              "01",
              "Bring in the documents",
              "Upload a resume or paste a job description.",
              "upload",
            ],
            ["02", "Review the details", "Inspect extracted fields and fill the gaps.", "file"],
            [
              "03",
              "Explore the matches",
              "Compare relevant skills and ranking evidence.",
              "people",
            ],
          ].map(([n, title, text, icon]) => (
            <div className="workflow-step" key={n}>
              <span className="step-number">{n}</span>
              <div>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
              <Icon name={icon} size={17} />
            </div>
          ))}
          <div className="workflow-caption">
            <span className="status-dot" /> Human judgment stays in the loop.
          </div>
        </section>
      </div>
      <div className="section-heading jobs-heading">
        <div>
          <h2>Roles worth exploring</h2>
          <p>Start with a job order. Follow the evidence.</p>
        </div>
        <button className="text-button" onClick={() => navigate("jobs")}>
          All job orders <Icon name="arrow" size={16} />
        </button>
      </div>
      <div className="job-preview-grid">
        {jobs
          .slice()
          .sort((a, b) => a.job_order_id.localeCompare(b.job_order_id))
          .slice(0, 3)
          .map((job, i) => (
            <article className="panel job-preview" key={job.id}>
              <div className="job-preview-top">
                <span className={`company-mark tone-${i}`}>{initials(job.organization_name)}</span>
                <span className="tag subtle">{job.domain || "Other"}</span>
              </div>
              <h3>{job.job_title}</h3>
              <p>{job.organization_name}</p>
              <div className="job-meta">
                <Icon name="pin" size={14} />
                {location(job)}
              </div>
              <div className="job-preview-bottom">
                <span>{job.skills.length} core skills</span>
                <button className="text-button" onClick={() => startMatch(job)}>
                  Find candidates <Icon name="arrow" size={15} />
                </button>
              </div>
            </article>
          ))}
      </div>
    </>
  );
}
