export function Icon({ name = "arrow", size = 20 }) {
  const paths = {
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.4" />
        <rect x="14" y="3" width="7" height="7" rx="1.4" />
        <rect x="3" y="14" width="7" height="7" rx="1.4" />
        <rect x="14" y="14" width="7" height="7" rx="1.4" />
      </>
    ),
    people: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M17 15a5 5 0 0 1 4 5" />
      </>
    ),
    briefcase: (
      <>
        <rect x="3" y="7" width="18" height="14" rx="2" />
        <path d="M8 7V4h8v3M3 12l9 4 9-4M12 12v5" />
      </>
    ),
    spark: (
      <>
        <path d="m12 3 2.8 6.2L21 12l-6.2 2.8L12 21l-2.8-6.2L3 12l6.2-2.8L12 3ZM20 2v4M18 4h4" />
      </>
    ),
    plug: (
      <>
        <path d="M8 3v5M16 3v5M5 8h14v3a7 7 0 0 1-14 0V8ZM12 18v4" />
      </>
    ),
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    plus: <path d="M12 5v14M5 12h14" />,
    upload: <path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5" />,
    file: (
      <>
        <path d="M14 2H5v20h14V7l-5-5ZM14 2v5h5M8 12h8M8 16h6" />
      </>
    ),
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5" />
      </>
    ),
    check: <path d="m5 12 4 4L20 5" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    pin: (
      <>
        <path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z" />
        <circle cx="12" cy="10" r="2" />
      </>
    ),
    code: <path d="m8 6-6 6 6 6M16 6l6 6-6 6m-3-16-2 20" />,
    chevrons: <path d="m8 9 4-4 4 4m-8 6 4 4 4-4" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    mail: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="m3 6 9 7 9-7" />
      </>
    ),
    chart: <path d="M3 3v18h18M7 16l4-5 4 2 6-8" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.arrow}
    </svg>
  );
}
export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <svg viewBox="0 0 32 32" width="29" height="29" fill="none">
          <path d="m7 7 9 0 9 9-9 9H7l9-9Z" fill="white" />
          <path d="m7 7 9 9-9 9" stroke="#8cafff" strokeWidth="3" />
        </svg>
      </span>
      <span>
        rolelens<span className="brand-period">.</span>
      </span>
    </div>
  );
}
export function Notice({ type = "info", children }) {
  return (
    <div className={`notice ${type}`} role={type === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}
export function Empty({ title = "Nothing here yet", children }) {
  return (
    <div className="empty">
      <Icon name="file" size={30} />
      <h3>{title}</h3>
      <p>{children || "Add a document to start building your workspace."}</p>
    </div>
  );
}
export function Tags({ items = [], max = 5 }) {
  return (
    <div className="tags">
      {items.slice(0, max).map((s, i) => (
        <span className="tag" key={`${s}-${i}`}>
          {s}
        </span>
      ))}
      {items.length > max && <span className="tag subtle">+{items.length - max}</span>}
    </div>
  );
}
export function initials(name = "?") {
  return name
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("");
}
export function location(record) {
  return (
    [record?.location?.city, record?.location?.state].filter(Boolean).join(", ") ||
    "Location not provided"
  );
}
export function role(record) {
  return record.experience?.[0]?.title || "Candidate profile";
}
