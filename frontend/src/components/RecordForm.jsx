function title(key) {
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace("Email Id", "Email")
    .replace("Phone No", "Phone");
}
export function Field({ label, value, onChange, type = "text", multiline = false, ...props }) {
  const control = {
    "aria-label": label,
    value: value ?? "",
    onChange: (e) =>
      onChange(
        type === "number"
          ? e.target.value === ""
            ? null
            : Number(e.target.value)
          : e.target.value,
      ),
    ...props,
  };
  return (
    <label className={`field ${multiline ? "wide" : ""}`}>
      <span>{label}</span>
      {multiline ? <textarea rows={3} {...control} /> : <input type={type} {...control} />}
    </label>
  );
}
export default function RecordForm({ kind, value, onChange }) {
  const job = kind === "job";
  function set(key, next) {
    onChange({ ...value, [key]: next });
  }
  const basics = job
    ? [
        "job_title",
        "organization_name",
        "domain",
        "work_arrangement",
        "employment_type",
        "years_required",
        "number_of_openings",
      ]
    : ["name", "email_id", "phone_no", "years_of_experience"];
  const arrays = job
    ? [
        "skills",
        "responsibilities",
        "qualifications",
        "certifications",
        "benefits",
        "additional_details",
        "physical_requirements",
      ]
    : ["skills", "tools", "certifications", "licenses", "languages"];
  return (
    <div className="record-form">
      <h3>{job ? "Role information" : "Profile information"}</h3>
      <div className="form-grid">
        {basics.map((key) => (
          <Field
            key={key}
            label={title(key)}
            value={value[key]}
            type={/years|number_of/.test(key) ? "number" : key === "email_id" ? "email" : "text"}
            min={0}
            step="any"
            onChange={(v) => set(key, v)}
          />
        ))}
      </div>
      <h3>Location</h3>
      <div className="form-grid">
        {[
          "city",
          "state",
          job ? "country" : "Country",
          "zip_code",
          "address_line_1",
          "address_line_2",
        ].map((key) => (
          <Field
            key={key}
            label={title(key)}
            value={value.location?.[key]}
            onChange={(v) => set("location", { ...value.location, [key]: v })}
          />
        ))}
      </div>
      {job && (
        <>
          <h3>Role summary</h3>
          <Field
            label="Summary"
            value={value.summary}
            multiline
            onChange={(v) => set("summary", v)}
          />
          <h3>Compensation</h3>
          <div className="form-grid">
            {["pay_text", "pay_rate_min", "pay_rate_max", "pay_frequency", "overtime"].map(
              (key) => (
                <Field
                  key={key}
                  label={title(key)}
                  value={value.compensation?.[key]}
                  type={key.includes("rate_") ? "number" : "text"}
                  min={0}
                  step="any"
                  onChange={(v) => set("compensation", { ...value.compensation, [key]: v })}
                />
              ),
            )}
          </div>
        </>
      )}
      <h3>{job ? "Requirements & details" : "Skills & credentials"}</h3>
      <p className="help-text">One item per line. Review extracted information before saving.</p>
      <div className="form-grid">
        {arrays.map((key) => (
          <Field
            key={key}
            label={title(key)}
            value={(value[key] || []).join("\n")}
            multiline
            onChange={(v) => set(key, v.split("\n"))}
          />
        ))}
      </div>
      {!job &&
        ["experience", "education"].map((key) => (
          <details key={key} open>
            <summary>
              {title(key)} <span className="count">{value[key]?.length || 0}</span>
            </summary>
            {(value[key] || []).map((entry, i) => (
              <div className="array-entry" key={i}>
                <div className="form-grid">
                  {(key === "experience"
                    ? ["title", "company", "start_date", "end_date", "summary"]
                    : ["degree", "institution", "graduation_year"]
                  ).map((k) => (
                    <Field
                      key={k}
                      label={title(k)}
                      value={entry[k]}
                      multiline={k === "summary"}
                      onChange={(v) =>
                        set(
                          key,
                          value[key].map((item, n) => (n === i ? { ...item, [k]: v } : item)),
                        )
                      }
                    />
                  ))}
                </div>
                <button
                  type="button"
                  className="text-button danger-text"
                  onClick={() =>
                    set(
                      key,
                      value[key].filter((_, n) => n !== i),
                    )
                  }
                >
                  Remove entry
                </button>
              </div>
            ))}
            <button
              type="button"
              className="button secondary compact"
              onClick={() => set(key, [...(value[key] || []), {}])}
            >
              + Add {key === "experience" ? "experience" : "education"}
            </button>
          </details>
        ))}
      {job && (
        <details>
          <summary>Schedule & other details</summary>
          <div className="form-grid">
            {[
              "hours_per_week",
              "hours_of_operation",
              "duration_weeks",
              "start_date",
              "end_date",
            ].map((key) => (
              <Field
                key={key}
                label={title(key)}
                value={value[key]}
                type={/hours_per_week|duration_weeks/.test(key) ? "number" : "text"}
                onChange={(v) => set(key, v)}
              />
            ))}
            {["will_sponsor", "will_relocate", "travel_required"].map((key) => (
              <label className="field" key={key}>
                <span>{title(key)}</span>
                <select
                  aria-label={title(key)}
                  value={value[key] == null ? "" : String(value[key])}
                  onChange={(e) =>
                    set(key, e.target.value === "" ? null : e.target.value === "true")
                  }
                >
                  <option value="">Not specified</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </label>
            ))}
          </div>
          <h3>Compliance</h3>
          <div className="form-grid">
            <Field
              label="Work authorization"
              value={value.compliance?.work_authorization}
              onChange={(v) => set("compliance", { ...value.compliance, work_authorization: v })}
            />
            {["drug_test", "background_check"].map((key) => (
              <label className="field" key={key}>
                <span>{title(key)}</span>
                <select
                  aria-label={title(key)}
                  value={value.compliance?.[key] == null ? "" : String(value.compliance[key])}
                  onChange={(e) =>
                    set("compliance", {
                      ...value.compliance,
                      [key]: e.target.value === "" ? null : e.target.value === "true",
                    })
                  }
                >
                  <option value="">Not specified</option>
                  <option value="true">Yes</option>
                  <option value="false">No</option>
                </select>
              </label>
            ))}
          </div>
          <h3>Per diem</h3>
          <div className="form-grid">
            {["amount_per_day", "frequency", "conditions"].map((key) => (
              <Field
                key={key}
                label={title(key)}
                value={value.compensation?.per_diem?.[key]}
                type={key === "amount_per_day" ? "number" : "text"}
                onChange={(v) =>
                  set("compensation", {
                    ...value.compensation,
                    per_diem: { ...value.compensation?.per_diem, [key]: v },
                  })
                }
              />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
export function cleanFields(fields) {
  const result = { ...fields };
  for (const key of [
    "skills",
    "tools",
    "certifications",
    "licenses",
    "languages",
    "responsibilities",
    "qualifications",
    "benefits",
    "additional_details",
    "physical_requirements",
  ])
    if (Array.isArray(result[key])) result[key] = result[key].map((s) => s.trim()).filter(Boolean);
  return result;
}
export function submission(record, fields) {
  return {
    source_file_name: record.file_name || record.source_file_name || "manual",
    source_file_type: record.file_type || record.source_file_type || ".txt",
    raw_text: record.raw_text || "",
    preview_text: record.preview_text || "",
    extraction_method: record.extraction_method || "manual_review",
    is_scanned_document: !!record.is_scanned_document,
    extracted_fields: cleanFields(fields),
  };
}
