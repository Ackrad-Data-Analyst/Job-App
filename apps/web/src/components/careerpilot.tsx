"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { EmployerDirectory, EducationPathways } from "./employer-directory";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Compass,
  LayoutDashboard,
  Search,
  BriefcaseBusiness,
  UserRound,
  SlidersHorizontal,
  ShieldCheck,
  Building2,
  ArrowUpRight,
  ArrowUp,
  ArrowDown,
  Plus,
  X,
  CalendarDays,
} from "lucide-react";
type R = Record<string, any>;
const STAGES = [
  "Discovered",
  "Under Review",
  "Shortlisted",
  "Draft Ready",
  "Approved",
  "Submitted",
  "Interview",
  "Offer",
  "Rejected",
  "Withdrawn",
];
const KINDS = [
  "experience",
  "education",
  "skills",
  "projects",
  "certifications",
  "languages",
  "identity",
  "rules",
];
const COUNTRIES = ["USA", "UAE"];
const NAV = [
  ["/", "Overview", LayoutDashboard],
  ["/search", "Find opportunities", Search],
  ["/roles", "Role explorer", Compass],
  ["/applications", "My applications", BriefcaseBusiness],
  ["/employers", "Employer research", Building2],
  ["/profile", "Career profile", UserRound],
  ["/preferences", "Preferences", SlidersHorizontal],
  ["/sources", "Job sources", ShieldCheck],
] as const;
export { api } from "@/lib/api";

function form(e: React.FormEvent<HTMLFormElement>): R {
  return Object.fromEntries(new FormData(e.currentTarget));
}
function date(value: string) {
  return value
    ? new Date(
        value.endsWith("Z") || value.includes("+") ? value : value + "Z",
      ).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "—";
}
function pay(j: R) {
  return j.salary_min != null || j.salary_max != null
    ? `${j.salary_currency || "Currency not stated"} ${j.salary_min ?? "?"} to ${j.salary_max ?? "?"} / ${j.salary_period || "period not stated"}`
    : j.salary || "Not published";
}
function Field({
  name,
  label,
  value = "",
  type = "text",
  required = false,
}: {
  name: string;
  label: string;
  value?: any;
  type?: string;
  required?: boolean;
}) {
  return (
    <label>
      {label}
      {type === "textarea" ? (
        <textarea
          name={name}
          defaultValue={String(value ?? "")}
          rows={5}
          maxLength={name === "description" ? 50000 : 10000}
        />
      ) : (
        <input
          name={name}
          defaultValue={value ?? ""}
          type={type}
          required={required}
          maxLength={
            name === "url" || name === "source_url" || type === "url"
              ? 2048
              : 240
          }
          step={type === "number" ? "0.01" : undefined}
        />
      )}
    </label>
  );
}
function Select({
  name,
  label,
  value = "",
  options,
}: {
  name: string;
  label: string;
  value?: string;
  options: string[];
}) {
  return (
    <label>
      {label}
      <select name={name} defaultValue={value}>
        {options.map((v) => (
          <option key={v} value={v}>
            {v || "Not stated"}
          </option>
        ))}
      </select>
    </label>
  );
}
function Check({
  name,
  label,
  value = false,
}: {
  name: string;
  label: string;
  value?: boolean;
}) {
  return (
    <label className="check">
      <input type="checkbox" name={name} defaultChecked={value} />
      <span>{label}</span>
    </label>
  );
}
function Badge({ value }: { value: string }) {
  return (
    <span
      className={
        "badge " +
        (value === "confirmed" || value === "Approved"
          ? "green"
          : value === "excluded" || value === "Rejected"
            ? "gray"
            : "")
      }
    >
      {value}
    </span>
  );
}
function Heading({
  title,
  eyebrow,
  description,
  children,
}: {
  title: string;
  eyebrow: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </div>
      {children}
    </div>
  );
}
function Fit({ value: f }: { value: R }) {
  return (
    <div className="fit stack">
      <div className="fit-score">
        <strong>
          {f.score ?? 0}
          <small>/100</small>
        </strong>
        <div>
          <h3>{f.recommendation || "Consider"}</h3>
          <p>Transparent local rubric. Your decision is final.</p>
        </div>
      </div>
      {f.blockers?.map((v: string, i: number) => (
        <p className="error" key={i}>
          <b>Requirement to resolve:</b> {v}
        </p>
      ))}
      {f.warnings?.map((v: string, i: number) => (
        <p className="warning" key={i}>
          {v}
        </p>
      ))}
      {["required", "preferred"].map(
        (k) =>
          f[k] && (
            <div className="skill-match" key={k}>
              <h3>{k === "required" ? "Required" : "Preferred"} skills</h3>
              <p>
                <b>I have (confirmed):</b>{" "}
                {f[k].confirmed.join(", ") || "No extracted matches"}
              </p>
              <p>
                <b>Supporting use under supervision:</b>{" "}
                {f[k].supporting?.join(", ") || "None extracted"}
              </p>
              <p>
                <b>Learning:</b> {f[k].learning.join(", ") || "None extracted"}
              </p>
              <p>
                <b>Missing:</b>{" "}
                {f[k].missing.join(", ") ||
                  "None extracted; check the complete text"}
              </p>
            </div>
          ),
      )}
      <p className="notice">
        <b>Work authorisation: {f.authorization || "unknown"}</b>
        <br />
        {f.authorization_note}
      </p>
      {f.opt_alignment && (
        <p className="notice">
          <b>OPT degree relationship: {f.opt_alignment.status}</b>
          <br />
          {f.opt_alignment.explanation}
          <br />
          <a href={f.opt_alignment.reference} target="_blank" rel="noreferrer">
            USCIS OPT reference ↗
          </a>
        </p>
      )}
      {f.salary_comparison && (
        <div className="salary">
          <b>
            {f.salary_comparison.min ?? "?"} to {f.salary_comparison.max ?? "?"}{" "}
            {f.salary_comparison.currency} {f.salary_comparison.period}
          </b>
          <p>
            {f.salary_comparison.label} {f.salary_comparison.minimum_status}
          </p>
          {f.salary_comparison.country_minimum && (
            <p>
              Country floor: {f.salary_comparison.country_minimum.value}{" "}
              {f.salary_comparison.country_minimum.currency}/
              {f.salary_comparison.country_minimum.period}
            </p>
          )}
          {f.salary_comparison.country_comparison && (
            <p>
              Rate in your floor's units:{" "}
              {f.salary_comparison.country_comparison.min ?? "?"}–
              {f.salary_comparison.country_comparison.max ?? "?"}{" "}
              {f.salary_comparison.country_comparison.currency}/
              {f.salary_comparison.country_comparison.period}
            </p>
          )}
          {f.salary_comparison.country_comparison && (
            <p>{f.salary_comparison.country_comparison.method}</p>
          )}
        </div>
      )}
      <p className="fine">
        {f.method ||
          "Keywords do not establish qualifications, registration, legal eligibility or authenticity."}
      </p>
    </div>
  );
}
export function CareerPilot() {
  const path = usePathname(),
    router = useRouter();
  const [data, setData] = useState<R | null>(null),
    [detail, setDetail] = useState<R | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [locked, setLocked] = useState(false);
  async function load() {
    try {
      const keys = [
        "profile",
        "preferences",
        "applications",
        "roles",
        "employers",
        "sources",
        "saved-searches",
        "reminders",
        "activity",
      ];
      const values = await Promise.all(keys.map((k) => api(k)));
      setData(Object.fromEntries(keys.map((k, i) => [k, values[i]])));
      if (path.startsWith("/applications/"))
        setDetail(await api(path.slice(1)));
      else setDetail(null);
      setLocked(false);
    } catch (e) {
      setError((e as Error).message);
      setLocked(true);
    }
  }
  useEffect(() => {
    void (async () => {
      const hash = new URLSearchParams(location.hash.slice(1));
      const code = hash.get("code");
      if (code) {
        history.replaceState(null, "", location.pathname);
        try {
          await api("unlock", { code }, "POST");
        } catch (e) {
          setError((e as Error).message);
          setLocked(true);
          return;
        }
      }
      await load();
    })();
  }, [path]);
  async function action(
    work: () => Promise<unknown>,
    success = "Saved locally. Nothing was sent.",
  ) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work();
      setMessage(success);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const ctx = { data: data!, detail, busy, action, router };
  if (!data)
    return (
      <main className="welcome">
        <section className="welcome-card">
          <div className="brand">
            <Compass />
            CareerPilot.
          </div>
          <p className="eyebrow">YOUR PRIVATE CAREER WORKSPACE</p>
          <h1>
            {locked ? "Start your next chapter." : "Opening your workspace…"}
          </h1>
          <p className="muted">
            Open the Start file on your computer. It opens a one-use unlock link
            automatically. If this session expired, stop and start again.
          </p>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <p className="notice">
            Your real experience. Your informed decisions. Your approval before
            applying.
          </p>
        </section>
      </main>
    );
  return (
    <div className="app">
      <aside className="sidebar">
        <Link className="brand" href="/">
          <span>
            <Compass />
          </span>
          CareerPilot.
        </Link>
        <p className="nav-caption">MY CAREER WORKSPACE</p>
        <nav aria-label="Navigation">
          {NAV.map(([href, label, Icon]) => (
            <Link
              key={href}
              href={href}
              className={
                (href === "/" ? path === "/" : path.startsWith(href))
                  ? "active"
                  : ""
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="guard">
          <ShieldCheck />
          <h3>Always on your terms.</h3>
          <p>
            Your real experience.
            <br />
            Your informed decisions.
            <br />
            Your approval before applying.
          </p>
          <small>PRIVATE BY DESIGN</small>
        </div>
        <p className="local-user">
          My private workspace
          <br />
          <small>Saved on this computer</small>
        </p>
      </aside>
      <div className="main-wrap">
        <header>
          <span>
            Workspace /{" "}
            <b>
              {NAV.find(([h]) =>
                h === "/" ? path === "/" : path.startsWith(h),
              )?.[1] || "Application"}
            </b>
          </span>
          <span className="local-pill">● Running locally</span>
        </header>
        <main className="content">
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="success">
              {message}
            </p>
          )}
          {path === "/" ? (
            <Overview {...ctx} />
          ) : path === "/profile" ? (
            <Profile {...ctx} />
          ) : path === "/preferences" ? (
            <Preferences {...ctx} />
          ) : path === "/roles" ? (
            <Roles {...ctx} />
          ) : path === "/sources" ? (
            <Sources {...ctx} />
          ) : path === "/employers" ? (
            <Employers {...ctx} />
          ) : path === "/search" ? (
            <SearchPage {...ctx} />
          ) : path === "/applications" ? (
            <>
              <Heading
                eyebrow="EVERY OPPORTUNITY, IN VIEW"
                title="Your applications."
                description="Keep decisions, documents and employer responses together."
              />
              <Capture {...ctx} />
              <Tracker applications={data.applications} />
            </>
          ) : detail ? (
            <ApplicationPage key={detail.id} {...ctx} a={detail} />
          ) : (
            <p className="notice">Loading application…</p>
          )}
        </main>
        <footer>
          CareerPilot · Engineering your next chapter
          <span>Private workspace · Manual submissions only</span>
        </footer>
      </div>
    </div>
  );
}
type Ctx = {
  data: R;
  detail: R | null;
  busy: boolean;
  action: (w: () => Promise<unknown>, s?: string) => Promise<void>;
  router: ReturnType<typeof useRouter>;
};
function Overview(c: Ctx) {
  const a = c.data.applications.filter((a: R) => !a.job.is_demo);
  const p = c.data.profile;
  const count = KINDS.filter((k) => !["identity", "rules"].includes(k))
    .flatMap((k) => p[k])
    .filter((f: R) => f.status === "confirmed").length;
  return (
    <>
      <Heading
        eyebrow="YOUR CAREER, WITH DIRECTION"
        title="A little clarity. A lot of possibility."
        description="Your experience in focus. Your opportunities in one place."
      >
        <Link className="btn primary" href="/search">
          Find opportunities <ArrowUpRight size={16} />
        </Link>
      </Heading>
      <section className="hero">
        <div>
          <span className="hero-tag">● ENGINEERING YOUR NEXT CHAPTER</span>
          <h2>
            Good opportunities.
            <br />
            Thoughtful applications.
          </h2>
          <p>
            A career built on your strengths and the facts you can stand behind.
          </p>
          <Link href="/roles">Explore related career paths →</Link>
        </div>
        <div className="compass-art" aria-hidden="true">
          ✧
        </div>
      </section>
      <div className="metrics">
        {[
          ["Opportunities saved", a.length],
          [
            "Ready for review",
            a.filter((x: R) => x.stage === "Draft Ready").length,
          ],
          ["Submissions recorded", a.filter((x: R) => x.submitted_at).length],
          [
            "Interviews & offers",
            a.filter((x: R) => ["Interview", "Offer"].includes(x.stage)).length,
          ],
        ].map(([label, n]) => (
          <article className="panel" key={label}>
            <p>{label}</p>
            <strong>{String(n).padStart(2, "0")}</strong>
            <small>You control every next step</small>
          </article>
        ))}
      </div>
      <div className="columns">
        <div>
          <section className="panel pad">
            <div className="section-heading">
              <h2>More than one way forward</h2>
              <Link href="/roles">Explore all ↗</Link>
            </div>
            <div className="cards">
              {c.data.roles.slice(0, 3).map((r: R) => (
                <Link
                  className="role-card"
                  href={
                    "/search?title=" +
                    encodeURIComponent(r.title) +
                    (/healthcare|hospital|business intelligence|operations analyst|supply chain/i.test(
                      r.title,
                    )
                      ? "&track=analytics"
                      : "")
                  }
                  key={r.title}
                >
                  <small>
                    {r.supported
                      ? "CONFIRMED KEYWORD SUPPORT"
                      : "DIRECTION TO EXPLORE"}
                  </small>
                  <h3>{r.title}</h3>
                  <p>
                    {r.evidence.join(" · ") ||
                      "Add confirmed facts to assess this route."}
                  </p>
                  <span>Explore vacancies ↗</span>
                </Link>
              ))}
            </div>
          </section>
          <Tracker applications={a} compact />
          <section className="panel pad">
            <h2>Your focus markets</h2>
            <div className="cards">
              {c.data.preferences.countries
                .filter((x: R) => x.enabled)
                .slice(0, 2)
                .map((x: R, i: number) => (
                  <article className="market" key={x.country}>
                    <small>PRIORITY {i + 1}</small>
                    <h3>{x.country}</h3>
                    <p>{x.regions}</p>
                    <span>Work authorisation: {x.authorization}</span>
                  </article>
                ))}
            </div>
          </section>
        </div>
        <aside>
          <section className="panel pad">
            <h2>A strong foundation</h2>
            <p className="muted">
              Build your search from facts you have checked.
            </p>
            <div className="foundation">
              <strong>{count}</strong> confirmed career facts
            </div>
            <Link href="/profile" className="btn secondary">
              Review my profile →
            </Link>
          </section>
          <section className="panel pad">
            <h2>Follow-up reminders</h2>
            {c.data.reminders
              .filter((r: R) => !r.completed)
              .slice(0, 6)
              .map((r: R) => (
                <article className="row" key={r.id}>
                  <Link href={"/applications/" + r.application_id}>
                    {r.title}
                    <small>{date(r.due_at)}</small>
                  </Link>
                  <button
                    className="btn secondary small"
                    onClick={() =>
                      c.action(() =>
                        api("reminders/" + r.id + "/complete", {}, "POST"),
                      )
                    }
                  >
                    Complete
                  </button>
                </article>
              ))}
            {!c.data.reminders.some((r: R) => !r.completed) && (
              <p className="muted">
                Your 7-day and 14-day reminders appear after an approved manual
                submission.
              </p>
            )}
            <p className="fine">Local reminders. No message is sent.</p>
          </section>
          <section className="panel pad">
            <h2>Recent activity</h2>
            {c.data.activity.slice(0, 5).map((v: R) => (
              <p className="activity" key={v.id}>
                {v.message}
                <small>{date(v.created_at)}</small>
              </p>
            ))}
          </section>
        </aside>
      </div>
    </>
  );
}
function Tracker({
  applications,
  compact = false,
}: {
  applications: R[];
  compact?: boolean;
}) {
  const [term, setTerm] = useState(""),
    [stage, setStage] = useState(""),
    [country, setCountry] = useState(""),
    [score, setScore] = useState(""),
    [after, setAfter] = useState(""),
    [board, setBoard] = useState(false),
    [demo, setDemo] = useState(false);
  const rows = applications.filter(
    (a) =>
      !!a.job.is_demo === demo &&
      (!term ||
        (a.job.title + " " + a.job.employer)
          .toLowerCase()
          .includes(term.toLowerCase())) &&
      (!stage || a.stage === stage) &&
      (!country || a.job.country === country) &&
      (!score || a.fit.score >= Number(score)) &&
      (!after || a.created_at.slice(0, 10) >= after),
  );
  const visible = compact ? rows.slice(0, 4) : rows;
  return (
    <section className="panel tracker">
      <div className="section-heading pad">
        <div>
          <h2>
            {compact ? "Your opportunity shortlist" : "Application tracker"}
          </h2>
          <p className="muted">
            {rows.length} records · You control every stage
          </p>
        </div>
        {!compact && (
          <div className="actions">
            <button
              className="btn secondary small"
              onClick={() => setBoard(!board)}
            >
              {board ? "Table view" : "Kanban board"}
            </button>
            <a className="btn secondary small" href="/api/tracker/export">
              Export CSV / Excel
            </a>
          </div>
        )}
      </div>
      {!compact && (
        <div className="filters">
          <input
            aria-label="Search applications"
            placeholder="Search role or employer…"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
          />
          <select
            aria-label="Stage filter"
            value={stage}
            onChange={(e) => setStage(e.target.value)}
          >
            <option value="">All stages</option>
            {STAGES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <select
            aria-label="Country filter"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
          >
            <option value="">All countries</option>
            {[...new Set(applications.map((a) => a.job.country))]
              .filter(Boolean)
              .map((s) => (
                <option key={s}>{s}</option>
              ))}
          </select>
          <input
            type="number"
            min={0}
            max={100}
            aria-label="Minimum score"
            placeholder="Minimum score"
            value={score}
            onChange={(e) => setScore(e.target.value)}
          />
          <input
            type="date"
            aria-label="Saved since"
            value={after}
            onChange={(e) => setAfter(e.target.value)}
          />
          <label className="check">
            <input
              type="checkbox"
              checked={demo}
              onChange={(e) => setDemo(e.target.checked)}
            />
            Demo only
          </label>
        </div>
      )}
      {demo && (
        <p className="warning">
          Demo area: fictional examples, never genuine openings.
        </p>
      )}
      {board && !compact ? (
        <div className="kanban">
          {STAGES.map((s) => (
            <section key={s}>
              <h3>{s}</h3>
              {visible
                .filter((a) => a.stage === s)
                .map((a) => (
                  <Link
                    className="kanban-card"
                    key={a.id}
                    href={"/applications/" + a.id}
                  >
                    <strong>{a.job.title}</strong>
                    <p>{a.job.employer}</p>
                    <small>
                      {a.job.country} · {a.fit.score}/100
                    </small>
                    <span>Review and move →</span>
                  </Link>
                ))}
            </section>
          ))}
        </div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>ROLE & EMPLOYER</th>
                <th>LOCATION</th>
                <th>STAGE</th>
                <th>SCORE</th>
                <th>SAVED</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((a) => (
                <tr key={a.id}>
                  <td>
                    <Link className="role-link" href={"/applications/" + a.id}>
                      {a.job.title}
                    </Link>
                    <small>{a.job.employer}</small>
                    <span className="source-status">
                      {a.job.is_demo
                        ? "FICTIONAL"
                        : a.job.verification === "verified"
                          ? "Manually verified"
                          : "Check original opening"}
                    </span>
                  </td>
                  <td>
                    {a.job.location}
                    <small>{a.job.country}</small>
                  </td>
                  <td>
                    <Badge value={a.stage} />
                  </td>
                  <td>
                    {a.fit.score}/100<small>{a.fit.recommendation}</small>
                  </td>
                  <td>{date(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!visible.length && (
        <div className="empty">
          <BriefcaseBusiness />
          <h3>Your next chapter is still unwritten.</h3>
          <p>Save an opportunity to start tracking it here.</p>
          <Link href="/search" className="btn primary">
            Find opportunities ↗
          </Link>
        </div>
      )}
    </section>
  );
}
function Profile(c: Ctx) {
  const p = c.data.profile;
  const [edit, setEdit] = useState<R | null>(null),
    [seed, setSeed] = useState("");
  const f = edit?.fact || {
    status: "unverified",
    allowed_on_resume: true,
    learning: false,
  };
  return (
    <>
      <Heading
        eyebrow="REAL FACTS. BETTER DIRECTION."
        title="Build your career foundation."
        description="Only confirmed, resume-allowed facts can support claims. Learning skills stay learning."
      />
      <p className="notice">
        Confirmed means checked by you. Unverified stays out of matching and
        documents. Excluded facts are retained for reference. Private notes are
        never resume claims.
      </p>
      <section className="panel pad">
        <h2>Your professional overview</h2>
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            const d = form(e);
            void c.action(() =>
              api(
                "profile",
                { ...d, allowed_on_resume: d.allowed_on_resume === "on" },
                "PUT",
              ),
            );
          }}
        >
          <div className="grid">
            <Field
              name="name"
              label="Name / display name"
              value={p.candidate.name}
              required
            />
            <Field
              name="headline"
              label="Professional headline"
              value={p.candidate.headline}
            />
          </div>
          <Field
            name="summary"
            label="Factual career summary"
            value={p.candidate.summary}
            type="textarea"
          />
          <Select
            name="status"
            label="Overview verification"
            value={p.candidate.status}
            options={["unverified", "confirmed", "excluded"]}
          />
          <Check
            name="allowed_on_resume"
            label="Allow confirmed overview on resumes"
            value={p.candidate.allowed_on_resume}
          />
          <Field
            name="note"
            label="Private overview note"
            value={p.candidate.note}
            type="textarea"
          />
          <button className="btn primary" disabled={c.busy}>
            Save overview
          </button>
        </form>
      </section>
      {KINDS.map((k) => (
        <section className="panel pad" key={k}>
          <div className="section-heading">
            <div>
              <h2>
                {k === "identity"
                  ? "Contact & identity"
                  : k === "rules"
                    ? "Private rules & unresolved questions"
                    : k === "projects"
                      ? "Projects / publications"
                      : k[0].toUpperCase() + k.slice(1)}
              </h2>
              <p className="muted">
                Keep uncertain dates and proficiency unverified.
              </p>
            </div>
            <button
              className="btn secondary small"
              onClick={() => setEdit({ kind: k })}
            >
              <Plus size={14} />
              Add fact
            </button>
          </div>
          {p[k].map((item: R) => (
            <article className="fact" key={item.id}>
              <div>
                <h3>
                  {item.title} <Badge value={item.status} />
                </h3>
                <p>
                  {item.organization}{" "}
                  {item.start_date && " · " + item.start_date}{" "}
                  {item.end_date && " to " + item.end_date}
                </p>
                <p className="preserve">{item.details}</p>
                <small>
                  {item.allowed_on_resume
                    ? "Resume allowed when confirmed"
                    : "Not allowed on resumes"}
                  {item.learning ? " · Currently learning" : ""}
                </small>
                {item.note && (
                  <p className="fine preserve">
                    <b>Private note:</b> {item.note}
                  </p>
                )}
              </div>
              <button
                className="btn secondary small"
                aria-label={"Edit " + item.title}
                onClick={() => setEdit({ kind: k, fact: item })}
              >
                Edit
              </button>
            </article>
          ))}
          {!p[k].length && (
            <p className="empty-small">No facts recorded in this category.</p>
          )}
        </section>
      ))}
      <details className="panel pad">
        <summary>Import a private profile seed or recovery block</summary>
        <p className="fine">
          Imports into an empty profile only. Existing edits are never
          overwritten. This stays on your computer.
        </p>
        <textarea
          aria-label="Private profile seed"
          rows={5}
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          placeholder="Paste JSON or your private recovery block"
        />
        <button
          className="btn secondary"
          onClick={() =>
            c.action(async () => {
              await api("profile-import", { data: seed }, "POST");
              setSeed("");
            }, "Private profile imported with original verification statuses.")
          }
        >
          Import private profile
        </button>
      </details>
      {edit && (
        <div className="overlay">
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Career fact editor"
            className="modal"
          >
            <div className="section-heading">
              <h2>
                {edit.fact ? "Edit" : "Add"} {edit.kind}
              </h2>
              <button
                className="icon-btn"
                aria-label="Close fact editor"
                onClick={() => setEdit(null)}
              >
                <X />
              </button>
            </div>
            <form
              key={edit.kind + (f.id || "new")}
              className="stack"
              onSubmit={(e) => {
                e.preventDefault();
                const d = form(e);
                void c.action(async () => {
                  await api(
                    "profile/" + edit.kind + (f.id ? "/" + f.id : ""),
                    {
                      ...d,
                      allowed_on_resume: d.allowed_on_resume === "on",
                      learning: d.learning === "on",
                    },
                    f.id ? "PUT" : "POST",
                  );
                  setEdit(null);
                });
              }}
            >
              <Field
                name="title"
                label="Title / degree / tool / registration"
                value={f.title}
                required
              />
              <Field
                name="organization"
                label="Organisation / institution"
                value={f.organization}
              />
              <div className="grid">
                <Field
                  name="start_date"
                  label="Start date (YYYY-MM or YYYY-MM-DD)"
                  value={f.start_date}
                />
                <Field
                  name="end_date"
                  label="End date (optional)"
                  value={f.end_date}
                />
              </div>
              <Field
                name="details"
                label="Factual details"
                value={f.details}
                type="textarea"
              />
              <Select
                name="status"
                label="Verification"
                value={f.status}
                options={["unverified", "confirmed", "excluded"]}
              />
              <Check
                name="allowed_on_resume"
                label="Allow on resumes once confirmed"
                value={f.allowed_on_resume}
              />
              <Check
                name="learning"
                label="Currently learning (never counts as already held)"
                value={f.learning}
              />
              <Field
                name="note"
                label="Private note"
                value={f.note}
                type="textarea"
              />
              <div className="actions">
                {f.id && (
                  <button
                    type="button"
                    className="btn danger"
                    onClick={() =>
                      c.action(async () => {
                        await api(
                          "profile/" + edit.kind + "/" + f.id,
                          undefined,
                          "DELETE",
                        );
                        setEdit(null);
                      })
                    }
                  >
                    Delete fact
                  </button>
                )}
                <button className="btn primary" disabled={c.busy}>
                  Save fact
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
function Preferences(c: Ctx) {
  const p = c.data.preferences;
  const [countries, setCountries] = useState<R[]>(p.countries),
    [drag, setDrag] = useState<number | null>(null);
  function move(i: number, j: number) {
    const copy = [...countries];
    const [item] = copy.splice(i, 1);
    copy.splice(j, 0, item);
    setCountries(copy);
  }
  function change(i: number, v: R) {
    setCountries(countries.map((x, j) => (j === i ? { ...x, ...v } : x)));
  }
  return (
    <>
      <Heading
        eyebrow="A SEARCH SHAPED AROUND YOU"
        title="Set your direction."
        description="Country priorities, career targets and private work-authorisation controls."
      />
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          const d = form(e);
          const lines = (k: string) =>
            String(d[k] || "")
              .split("\n")
              .map((v) => v.trim())
              .filter(Boolean);
          let rates;
          try {
            rates = Object.fromEntries(
              lines("rates").map((v) => {
                const [k, n] = v.split("=");
                return [k.trim().toUpperCase(), Number(n)];
              }),
            );
          } catch {
            void c.action(async () => {
              throw new Error(
                "Enter exchange rates as USD=1.35, one per line, using your own dated rates.",
              );
            });
            return;
          }
          const body = {
            ...p,
            home_base: d.home_base,
            planned_move_date: d.planned_move_date,
            mobility_notes: d.mobility_notes,
            max_job_age_days: Number(d.max_job_age_days),
            max_applicant_count: Number(d.max_applicant_count),
            older_job_applicant_threshold: Number(
              d.older_job_applicant_threshold,
            ),
            include_unknown_applicant_count:
              d.include_unknown_applicant_count === "on",
            include_unknown_posted_date: d.include_unknown_posted_date === "on",
            use_apply_clicks_as_proxy: d.use_apply_clicks_as_proxy === "on",
            max_commute_minutes: d.max_commute_minutes
              ? Number(d.max_commute_minutes)
              : null,
            relocation_preference: d.relocation_preference,
            location_priorities: String(d.location_priorities || "")
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean),
            countries,
            target_titles: lines("target_titles"),
            interests: String(d.interests)
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean),
            excluded_employers: lines("excluded_employers"),
            excluded_terms: lines("excluded_terms"),
            comparison_currency: d.comparison_currency,
            exchange_rates: rates,
            exchange_rate_date: d.exchange_rate_date,
            earliest_start: d.earliest_start,
            employment_type: d.employment_type,
            early_career_only: d.early_career_only === "on",
            languages_on_resume: d.languages_on_resume === "on",
            canadian_location: false,
          };
          void c.action(
            () => api("preferences", body, "PUT"),
            "Preferences saved. Blank country salary minimums remain inactive.",
          );
        }}
      >
        <section className="panel pad">
          <div className="section-heading">
            <div>
              <h2>Country priorities</h2>
              <p className="muted">
                Drag to reorder, or use the arrows. Notes never print on
                resumes.
              </p>
            </div>
            <button
              type="button"
              className="btn secondary small"
              disabled={COUNTRIES.every((country) =>
                countries.some((c) => c.country === country),
              )}
              onClick={() =>
                setCountries([
                  ...countries,
                  {
                    country:
                      COUNTRIES.find(
                        (country) =>
                          !countries.some((c) => c.country === country),
                      ) || "USA",
                    regions: "",
                    enabled: true,
                    authorization: "unknown",
                    authorization_note: "",
                    min_salary: null,
                    currency: "USD",
                    template: "USA",
                  },
                ])
              }
            >
              Add country
            </button>
          </div>
          {countries.map((x, i) => (
            <article
              className="country"
              key={i}
              draggable
              onDragStart={() => setDrag(i)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (drag !== null) move(drag, i);
                setDrag(null);
              }}
            >
              <div className="section-heading">
                <strong>Priority {i + 1}</strong>
                <div className="actions">
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label={"Move " + x.country + " up"}
                    disabled={!i}
                    onClick={() => move(i, i - 1)}
                  >
                    <ArrowUp size={16} />
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label={"Move " + x.country + " down"}
                    disabled={i === countries.length - 1}
                    onClick={() => move(i, i + 1)}
                  >
                    <ArrowDown size={16} />
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label={"Remove " + x.country}
                    disabled={countries.length === 1}
                    onClick={() =>
                      setCountries(countries.filter((_, j) => j !== i))
                    }
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
              <div className="grid">
                <label>
                  Country
                  <input
                    value={x.country}
                    required
                    minLength={2}
                    onChange={(e) => change(i, { country: e.target.value })}
                  />
                </label>
                <label>
                  Regions, highest priority first
                  <input
                    value={x.regions}
                    onChange={(e) => change(i, { regions: e.target.value })}
                  />
                </label>
                <label>
                  Work authorisation
                  <select
                    value={x.authorization}
                    onChange={(e) =>
                      change(i, { authorization: e.target.value })
                    }
                  >
                    {[
                      "unknown",
                      "pending",
                      "needs sponsorship",
                      "authorised",
                    ].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Minimum advertised pay, before tax (optional)
                  <input
                    type="number"
                    min={0}
                    value={x.min_salary ?? ""}
                    onChange={(e) =>
                      change(i, {
                        min_salary: e.target.value
                          ? Number(e.target.value)
                          : null,
                      })
                    }
                  />
                </label>
                <label>
                  Minimum-pay period
                  <select
                    value={x.min_salary_period || "year"}
                    onChange={(e) =>
                      change(i, { min_salary_period: e.target.value })
                    }
                  >
                    {["month", "year", "hour"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Work-authorisation route (private)
                  <input
                    value={x.authorization_route || ""}
                    onChange={(e) =>
                      change(i, { authorization_route: e.target.value })
                    }
                  />
                </label>
                <label>
                  Work start not before
                  <input
                    type="date"
                    value={x.work_start_not_before || ""}
                    onChange={(e) =>
                      change(i, { work_start_not_before: e.target.value })
                    }
                  />
                </label>
                <label>
                  Authorisation expiry (leave blank if not recorded)
                  <input
                    type="date"
                    value={x.authorization_expiry || ""}
                    onChange={(e) =>
                      change(i, { authorization_expiry: e.target.value })
                    }
                  />
                </label>
                <label>
                  Salary currency
                  <input
                    maxLength={3}
                    pattern="[A-Z]{3}"
                    value={x.currency}
                    onChange={(e) =>
                      change(i, { currency: e.target.value.toUpperCase() })
                    }
                  />
                </label>
                <label>
                  Default template
                  <select
                    value={x.template || x.country}
                    onChange={(e) => change(i, { template: e.target.value })}
                  >
                    {COUNTRIES.map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="check">
                <input
                  type="checkbox"
                  checked={x.enabled}
                  onChange={(e) => change(i, { enabled: e.target.checked })}
                />
                Include this country in searches
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={x.allow_lower_for_early_career || false}
                  onChange={(e) =>
                    change(i, {
                      allow_lower_for_early_career: e.target.checked,
                    })
                  }
                />
                Retain below-floor early-career/internship roles for manual
                review; progression is not assumed
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={x.allow_internships || false}
                  onChange={(e) =>
                    change(i, { allow_internships: e.target.checked })
                  }
                />
                Allow relevant internships in this country
              </label>
              <label>
                Private authorisation note
                <textarea
                  rows={2}
                  maxLength={2000}
                  value={x.authorization_note}
                  onChange={(e) =>
                    change(i, { authorization_note: e.target.value })
                  }
                />
              </label>
            </article>
          ))}
        </section>
        <section className="panel pad stack">
          <h2>Home base and location preferences</h2>
          <p className="fine">
            Search settings only. These fields do not change the location on
            your resume or establish work eligibility.
          </p>
          <div className="grid">
            <Field
              name="home_base"
              label="Planned home base"
              value={p.home_base || ""}
            />
            <Field
              name="location_priorities"
              label="Location priorities, comma-separated"
              value={(p.location_priorities || []).join(", ")}
            />
            <Field
              name="max_commute_minutes"
              label="Maximum daily commute in minutes (leave blank until decided)"
              type="number"
              value={p.max_commute_minutes ?? ""}
            />
            <Select
              name="relocation_preference"
              label="Relocation / rotation preference"
              value={p.relocation_preference || "unspecified"}
              options={["unspecified", "near home", "open", "rotational"]}
            />
          </div>
          <Field
            name="planned_move_date"
            label="Planned move date (private)"
            type="date"
            value={p.planned_move_date || ""}
          />
          <Field
            name="mobility_notes"
            label="Private mobility preferences"
            type="textarea"
            value={p.mobility_notes || ""}
          />
          <h2>Freshness and competition</h2>
          <div className="grid">
            <Field
              name="max_job_age_days"
              label="Normal maximum posting age (days)"
              type="number"
              value={p.max_job_age_days ?? 5}
            />
            <Field
              name="max_applicant_count"
              label="Maximum reported application count"
              type="number"
              value={p.max_applicant_count ?? 100}
            />
            <Field
              name="older_job_applicant_threshold"
              label="Allow older jobs only below this reported count"
              type="number"
              value={p.older_job_applicant_threshold ?? 20}
            />
          </div>
          <Check
            name="include_unknown_applicant_count"
            label="Include fresh employer jobs with applicant count not reported"
            value={p.include_unknown_applicant_count ?? true}
          />
          <Check
            name="include_unknown_posted_date"
            label="Also include unknown posting dates (explicit freshness exception)"
            value={p.include_unknown_posted_date ?? false}
          />
          <Check
            name="use_apply_clicks_as_proxy"
            label="Use clearly labelled apply-click counts as a competition proxy"
            value={p.use_apply_clicks_as_proxy ?? false}
          />
          <p className="fine">
            Apply clicks are not completed applications. Employer sites often
            publish no counts. Updated dates are not treated as new posting
            dates. Older posts need a qualifying published count below your
            exception threshold.
          </p>
          <h2>Career focus</h2>
          <div className="grid">
            <Field
              name="target_titles"
              label="Target titles (one per line)"
              value={p.target_titles.join("\n")}
              type="textarea"
            />
            <div>
              <Field
                name="excluded_employers"
                label="Excluded employers (one per line)"
                value={p.excluded_employers.join("\n")}
                type="textarea"
              />
              <Field
                name="excluded_terms"
                label="Excluded title terms (one per line)"
                value={p.excluded_terms.join("\n")}
                type="textarea"
              />
            </div>
          </div>
          <Field
            name="interests"
            label="Interests (comma-separated)"
            value={p.interests.join(", ")}
            type="textarea"
          />
          <div className="grid">
            <Field
              name="earliest_start"
              label="Earliest start"
              value={p.earliest_start}
              type="date"
            />
            <Select
              name="employment_type"
              label="Employment preference"
              value={p.employment_type}
              options={["Full-time", "Any"]}
            />
          </div>
          <Check
            name="early_career_only"
            label="Focus on junior, graduate and early-career roles"
            value={p.early_career_only}
          />
        </section>
        <section className="panel pad stack">
          <h2>Salary comparison</h2>
          <p className="muted">
            Only published numbers are compared. Enter your own dated rates: one
            source currency equals units of your comparison currency. No rate is
            guessed.
          </p>
          <div className="grid">
            <Field
              name="comparison_currency"
              label="Comparison currency"
              value={p.comparison_currency}
            />
            <Field
              name="exchange_rate_date"
              label="Exchange rate date"
              value={p.exchange_rate_date}
              type="date"
            />
          </div>
          <Field
            name="rates"
            label="Exchange rates, one per line (for example USD=1.35)"
            value={Object.entries(p.exchange_rates)
              .map(([k, v]) => `${k}=${v}`)
              .join("\n")}
            type="textarea"
          />
          <Check
            name="languages_on_resume"
            label="Include confirmed languages on resumes"
            value={p.languages_on_resume}
          />
        </section>
        <button className="btn primary" disabled={c.busy}>
          Save preferences
        </button>
      </form>
    </>
  );
}
function Roles(c: Ctx) {
  return (
    <>
      <Heading
        eyebrow="CONFIRMED EVIDENCE. REALISTIC DIRECTIONS."
        title="Explore your career paths."
        description="Career directions and gaps, not live vacancies or guaranteed eligibility."
      />
      <EducationPathways catalog={c.data.sources.catalog} />
      {[...new Set(c.data.roles.map((r: R) => r.family))].map((f) => (
        <section className="panel pad" key={String(f)}>
          <h2>{String(f)}</h2>
          <div className="cards">
            {c.data.roles
              .filter((r: R) => r.family === f)
              .map((r: R) => (
                <article className="role-card" key={r.title}>
                  <small>
                    {r.supported
                      ? "CONFIRMED KEYWORD SUPPORT"
                      : "MORE EVIDENCE NEEDED"}
                  </small>
                  <h3>{r.title}</h3>
                  <p>
                    {r.evidence.join(" · ") ||
                      "No confirmed keyword support yet."}
                  </p>
                  <details>
                    <summary>Confirmed facts & gaps</summary>
                    {r.facts.map((x: R) => (
                      <p key={x.id}>
                        <b>{x.title}</b>
                        <br />
                        {x.organization}
                      </p>
                    ))}
                    {r.gaps.map((x: string) => (
                      <p key={x}>Check: {x}</p>
                    ))}
                  </details>
                  <Link
                    href={
                      "/search?title=" +
                      encodeURIComponent(r.title) +
                      (/healthcare|hospital|business intelligence|operations analyst|supply chain/i.test(
                        r.title,
                      )
                        ? "&track=analytics"
                        : "")
                    }
                  >
                    Search this title →
                  </Link>
                </article>
              ))}
          </div>
        </section>
      ))}
    </>
  );
}
function Sources(c: Ctx) {
  const s = c.data.sources;
  return (
    <>
      <Heading
        eyebrow="GO TO THE SOURCE"
        title="Build a reliable search."
        description="Direct employer career pages, documented employer feeds and government sources. Page checks and live vacancies are shown separately."
      />
      <EmployerDirectory
        catalog={s.catalog}
        preferences={c.data.preferences}
        busy={c.busy}
        action={c.action}
      />
      <section className="panel pad">
        <div className="section-heading">
          <h2>Employer boards</h2>
          <button
            className="btn secondary"
            disabled={c.busy}
            onClick={() =>
              c.action(async () => {
                const r = await api("sources/bootstrap", {}, "POST");
                if (r.results.some((v: R) => !v.ok))
                  throw new Error(
                    "Some boards could not be reached. Their errors appear below; try again later.",
                  );
              }, "Employer boards checked against their public endpoints.")
            }
          >
            Check starter boards
          </button>
        </div>
        <p className="muted">
          Legacy starter metadata dates from 16 October 2026. Recheck the source
          before relying on it. The directory above covers additional employers;
          only successfully checked supported feeds enter automatic searches.
        </p>
        {s.feeds.map((f: R) => (
          <article className="feed row" key={f.id}>
            <div>
              <h3>{f.employer}</h3>
              <p>
                {f.provider} · {f.slug}
              </p>
              <small>
                {f.enabled ? "Enabled" : "Disabled"} · Last check{" "}
                {date(f.verified_at)}
              </small>
              {f.last_error && <p className="error">{f.last_error}</p>}
            </div>
            <div className="actions">
              <button
                className="btn secondary small"
                disabled={c.busy}
                onClick={() =>
                  c.action(async () => {
                    const r = await api(
                      "sources/feeds/" + f.id + "/verify",
                      {},
                      "POST",
                    );
                    if (!r.ok) throw new Error(r.message);
                  })
                }
              >
                Verify feed
              </button>
              <button
                className="btn secondary small"
                disabled={c.busy}
                onClick={() =>
                  c.action(() =>
                    api("sources/feeds/" + f.id, undefined, "DELETE"),
                  )
                }
              >
                Remove
              </button>
            </div>
          </article>
        ))}
        <details>
          <summary>Add an employer board</summary>
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              const d = form(e);
              void c.action(() => api("sources/feeds", d, "POST"));
            }}
          >
            <div className="grid">
              <Field name="employer" label="Employer name" required />
              <Select
                name="provider"
                label="Provider"
                value="smartrecruiters"
                options={Object.keys(s.providers)}
              />
              <Field name="slug" label="Published board identifier" required />
            </div>
            <p className="fine">
              Copy the identifier from the employer's public careers board. The
              new board remains disabled until a successful public read.
            </p>
            <button className="btn primary" disabled={c.busy}>
              Add disabled board
            </button>
          </form>
        </details>
      </section>
      <div className="cards">
        {s.apis.map((a: R) => (
          <article className="panel pad" key={a.name}>
            <Badge
              value={a.configured ? "Configured" : "Optional key needed"}
            />
            <h2>{a.name}</h2>
            <p>{a.countries}</p>
            <a href={a.docs} target="_blank" rel="noreferrer">
              Official documentation ↗
            </a>
          </article>
        ))}
      </div>
      <section className="panel pad">
        <h2>Private configuration</h2>
        <p>{s.ai_mode}</p>
        <p>
          Optional keys belong in <code>data/private/.env</code>. Stop and start
          CareerPilot after changing them. Keys are never displayed here.
        </p>
        <details>
          <summary>Public provider documentation</summary>
          {Object.entries(s.providers).map(([name, v]) => (
            <p key={name}>
              <a href={(v as R).docs} target="_blank" rel="noreferrer">
                {name} ↗
              </a>{" "}
              · {(v as R).countries}
            </p>
          ))}
        </details>
      </section>
    </>
  );
}
function Employers(c: Ctx) {
  const [edit, setEdit] = useState<R | null>(null),
    [contacts, setContacts] = useState<R[]>([]);
  function open(e: R) {
    setEdit(e);
    setContacts(e.contacts || []);
  }
  function update(i: number, v: R) {
    setContacts(contacts.map((x, j) => (j === i ? { ...x, ...v } : x)));
  }
  return (
    <>
      <Heading
        eyebrow="UNDERSTAND THE ORGANISATION"
        title="Employer research."
        description="Record public evidence, research notes and contacts you have actually verified."
      >
        <button className="btn primary" onClick={() => open({})}>
          Add employer
        </button>
      </Heading>
      <div className="cards">
        {c.data.employers.map((e: R) => (
          <article className="panel pad" key={e.id}>
            <h2>{e.name}</h2>
            <p>
              {e.sector || "Sector not researched"} ·{" "}
              {e.size || "Size not researched"}
            </p>
            <p>{e.countries.join(", ")}</p>
            <p className="prewrap">
              {e.research_notes || "No research notes yet."}
            </p>
            <div className="actions">
              {e.website && (
                <a href={e.website} target="_blank" rel="noreferrer">
                  Website ↗
                </a>
              )}
              {e.careers_page && (
                <a href={e.careers_page} target="_blank" rel="noreferrer">
                  Careers ↗
                </a>
              )}
            </div>
            {e.contacts.map((p: R, i: number) => (
              <p key={i}>
                <b>{p.name}</b> · {p.role}
                <br />
                {p.verified ? "Owner verified" : "Unverified"} ·{" "}
                <a href={p.source_url} target="_blank" rel="noreferrer">
                  Published source ↗
                </a>
              </p>
            ))}
            <button className="btn secondary small" onClick={() => open(e)}>
              Edit research
            </button>
          </article>
        ))}
      </div>
      {edit && (
        <div className="overlay">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Employer editor"
          >
            <div className="section-heading">
              <h2>Employer research</h2>
              <button
                aria-label="Close employer editor"
                className="icon-btn"
                onClick={() => setEdit(null)}
              >
                <X />
              </button>
            </div>
            <form
              className="stack"
              onSubmit={(e) => {
                e.preventDefault();
                const d = form(e);
                void c.action(async () => {
                  await api(
                    "employers" + (edit.id ? "/" + edit.id : ""),
                    {
                      ...d,
                      countries: String(d.countries)
                        .split(",")
                        .map((x) => x.trim())
                        .filter(Boolean),
                      contacts,
                    },
                    edit.id ? "PUT" : "POST",
                  );
                  setEdit(null);
                });
              }}
            >
              <Field
                name="name"
                label="Employer name"
                value={edit.name}
                required
              />
              <div className="grid">
                <Field
                  name="website"
                  label="Website"
                  value={edit.website}
                  type="url"
                />
                <Field
                  name="careers_page"
                  label="Careers page"
                  value={edit.careers_page}
                  type="url"
                />
                <Field name="sector" label="Sector" value={edit.sector} />
                <Field
                  name="size"
                  label="Company size (published)"
                  value={edit.size}
                />
              </div>
              <Field
                name="countries"
                label="Countries (comma-separated)"
                value={edit.countries?.join(", ")}
              />
              <Field
                name="public_feed"
                label="Published board identifier"
                value={edit.public_feed}
              />
              <Field
                name="research_notes"
                label="Private research and source notes"
                value={edit.research_notes}
                type="textarea"
              />
              <h3>Owner-sourced contacts</h3>
              <p className="fine">
                Use a public employer or directory source. Do not guess email
                addresses. Salutations are optional and used only when verified.
              </p>
              {contacts.map((p, i) => (
                <article className="country stack" key={i}>
                  <div className="grid">
                    {[
                      ["name", "Full name"],
                      ["role", "Role"],
                      ["email", "Published email (optional)"],
                      ["source_url", "Published source URL (required)"],
                      [
                        "salutation",
                        "Known salutation (Mr. Surname or Ms. Surname)",
                      ],
                    ].map(([k, l]) => (
                      <label key={k}>
                        {l}
                        <input
                          value={p[k]}
                          required={k === "name" || k === "source_url"}
                          type={
                            k === "source_url"
                              ? "url"
                              : k === "email"
                                ? "email"
                                : "text"
                          }
                          onChange={(e) => update(i, { [k]: e.target.value })}
                        />
                      </label>
                    ))}
                  </div>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={p.verified}
                      onChange={(e) =>
                        update(i, { verified: e.target.checked })
                      }
                    />
                    I checked this contact against the published source
                  </label>
                  <button
                    type="button"
                    className="btn secondary small"
                    onClick={() =>
                      setContacts(contacts.filter((_, j) => j !== i))
                    }
                  >
                    Remove contact
                  </button>
                </article>
              ))}
              <button
                type="button"
                className="btn secondary"
                onClick={() =>
                  setContacts([
                    ...contacts,
                    {
                      name: "",
                      role: "",
                      email: "",
                      source_url: "",
                      salutation: "",
                      verified: false,
                    },
                  ])
                }
              >
                Add published contact
              </button>
              <button className="btn primary" disabled={c.busy}>
                Save employer research
              </button>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
const emptyJob = {
  title: "",
  employer: "",
  country: "USA",
  location: "",
  url: "",
  description: "",
  source: "Manual capture",
  salary: "Not published",
  salary_min: null,
  salary_max: null,
  salary_currency: "",
  salary_period: "",
  closing_date: "",
  published_at: "",
  published_at_kind: "unknown",
  published_at_evidence: "",
  applicant_count: null,
  applicant_metric: "unknown",
  applicant_count_relation: "exact",
  applicant_count_evidence: "",
};
function jobBody(d: R) {
  return {
    ...emptyJob,
    ...Object.fromEntries(
      Object.keys(emptyJob).map((k) => [
        k,
        k === "salary_min" || k === "salary_max" || k === "applicant_count"
          ? d[k] === "" || d[k] == null
            ? null
            : Number(d[k])
          : (d[k] ?? emptyJob[k as keyof typeof emptyJob]),
      ]),
    ),
  };
}
function JobFields({ job: j }: { job: R }) {
  return (
    <>
      <div className="grid">
        <Field name="title" label="Job title" value={j.title} required />
        <Field name="employer" label="Employer" value={j.employer} required />
        <Select
          name="country"
          label="Country"
          value={j.country}
          options={COUNTRIES}
        />
        <Field name="location" label="City / region" value={j.location} />
      </div>
      <Field name="url" label="Original job URL" value={j.url} type="url" />
      <Field
        name="description"
        label="Full job description"
        value={j.description}
        type="textarea"
      />
      <details>
        <summary>Published posting date and application-count evidence</summary>
        <div className="grid">
          <Field
            name="published_at"
            label="Published posting date or original relative date text"
            value={j.published_at}
          />
          <Select
            name="published_at_kind"
            label="Date meaning"
            value={j.published_at_kind || "unknown"}
            options={[
              "unknown",
              "posted",
              "released",
              "updated",
              "owner reported",
            ]}
          />
          <Field
            name="published_at_evidence"
            label="Date source / evidence"
            value={j.published_at_evidence}
          />
          <Field
            name="applicant_count"
            label="Published application or click count (blank means unknown)"
            type="number"
            value={j.applicant_count}
          />
          <Select
            name="applicant_metric"
            label="What the displayed number measures"
            value={j.applicant_metric || "unknown"}
            options={["unknown", "applications", "apply clicks"]}
          />
          <Select
            name="applicant_count_relation"
            label="Count qualifier"
            value={j.applicant_count_relation || "exact"}
            options={["exact", "more than", "at least", "less than"]}
          />
          <Field
            name="applicant_count_evidence"
            label="Count source / evidence"
            value={j.applicant_count_evidence}
          />
        </div>
        <p className="fine">
          Enter only what the source displays. “People clicked apply” is not a
          completed-application count. No counts are invented when the source
          does not report them.
        </p>
      </details>
      <details>
        <summary>Source-stated pay and closing date</summary>
        <div className="grid">
          <Field name="salary" label="Published salary text" value={j.salary} />
          <Field
            name="salary_min"
            label="Published minimum (optional)"
            value={j.salary_min}
            type="number"
          />
          <Field
            name="salary_max"
            label="Published maximum (optional)"
            value={j.salary_max}
            type="number"
          />
          <Field
            name="salary_currency"
            label="Currency code (USD or AED)"
            value={j.salary_currency}
          />
          <Select
            name="salary_period"
            label="Pay period"
            value={j.salary_period}
            options={["", "year", "month", "hour"]}
          />
          <Field
            name="closing_date"
            label="Closing date, if stated"
            value={j.closing_date}
          />
          <Field name="source" label="Source name" value={j.source} />
        </div>
      </details>
    </>
  );
}
function Capture(c: Ctx) {
  const [open, setOpen] = useState(false),
    [job, setJob] = useState<R>({ ...emptyJob }),
    [url, setUrl] = useState(""),
    [permitted, setPermitted] = useState(false),
    [revision, setRevision] = useState(0);
  return (
    <section className="panel pad capture">
      <div className="section-heading">
        <div>
          <h2>Found an opportunity?</h2>
          <p className="muted">
            Paste the description or save an original job URL.
          </p>
        </div>
        <button className="btn secondary" onClick={() => setOpen(!open)}>
          {open ? "Close" : "Add a job manually"} <Plus size={16} />
        </button>
      </div>
      {open && (
        <div className="stack">
          <div className="notice">
            <label>
              Read a permitted public job page
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://employer.example/careers/…"
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={permitted}
                onChange={(e) => setPermitted(e.target.checked)}
              />
              This page permits public access. I want to read this single job.
            </label>
            <button
              className="btn secondary"
              disabled={c.busy || !url || !permitted}
              onClick={() =>
                c.action(async () => {
                  const r = await api("capture", { url, permitted }, "POST");
                  setJob({ ...emptyJob, ...r });
                  setRevision((x) => x + 1);
                }, "Source text loaded. Review it below before saving.")
              }
            >
              Read job page
            </button>
            <p className="fine">
              If access is restricted, paste the text yourself. No logins or
              access controls are bypassed.
            </p>
          </div>
          <form
            className="stack"
            key={revision}
            onSubmit={(e) => {
              e.preventDefault();
              const d = jobBody(form(e));
              void c.action(async () => {
                const a = await api("jobs", d, "POST");
                setOpen(false);
                c.router.push("/applications/" + a.id);
              }, "Job saved for your review. Authenticity is not yet confirmed.");
            }}
          >
            <JobFields job={job} />
            <button className="btn primary" disabled={c.busy}>
              Save job for review
            </button>
          </form>
        </div>
      )}
    </section>
  );
}
function Results({ result, c }: { result: R; c: Ctx }) {
  async function save(j: R) {
    let full = j;
    if (
      j.source?.toLowerCase().includes("smartrecruiters") ||
      j.source?.toLowerCase().includes("workday")
    ) {
      const detail = await api(
        "capture",
        { url: j.url, permitted: true },
        "POST",
      );
      full = { ...j, ...detail };
      if (!detail.published_at) {
        full.published_at = j.published_at;
        full.published_at_kind = j.published_at_kind;
        full.published_at_evidence = j.published_at_evidence;
      }
    }
    full.employer = full.employer || j.employer;
    const a = await api("jobs", jobBody(full), "POST");
    c.router.push("/applications/" + a.id);
  }
  return (
    <>
      <p className="notice">
        {result.coverage ||
          "Results from an on-demand saved search batch. Review the complete original posting."}
      </p>
      {result.errors?.map((x: string, i: number) => (
        <p className="error" key={i}>
          {x}
        </p>
      ))}
      {result.links?.length > 0 && (
        <div className="actions wrap">
          {result.links.map((l: R) => (
            <a
              className="btn secondary small"
              key={l.name || l.label}
              href={l.url}
              target="_blank"
              rel="noreferrer"
            >
              {l.name || l.label} ↗
            </a>
          ))}
        </div>
      )}
      {result.filtered && (
        <section className="panel pad">
          <h2>What this search covered</h2>
          <p>
            {result.jobs.length} displayed / {result.total} matching live
            postings · {result.retrieved} source rows retrieved ·{" "}
            {result.target_count} separate employer career-page targets
          </p>
          <details>
            <summary>Source coverage, pagination limits and filtering</summary>
            {result.source_checks?.map((x: R) => (
              <p key={x.employer}>
                <b>{x.employer}</b>: {x.status}; {x.returned} returned;{" "}
                {x.pages ?? 0} pages
                {x.truncated ? " · partial source window" : ""}
              </p>
            ))}
            <p>
              Excluded by rule:{" "}
              {Object.entries(result.filtered)
                .map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`)
                .join(" · ")}
            </p>
            {Object.entries(result.screening_rejections || {}).map(
              ([reason, count]) => (
                <p key={reason}>
                  {reason}: {String(count)}
                </p>
              ),
            )}
            <p>
              No omitted source or directory link is counted as a live vacancy.
            </p>
          </details>
        </section>
      )}
      <div className="search-results">
        {result.jobs?.map((j: R, i: number) => (
          <article className="panel pad" key={j.url || i}>
            <div className="section-heading">
              <div>
                <small>
                  {j.employer} · {j.source}
                </small>
                <h2>{j.title}</h2>
                <p>
                  {j.location} · {j.country}
                </p>
              </div>
              <Badge value={j.fit?.recommendation || "Consider"} />
            </div>
            <p className="salary">{pay(j)}</p>
            <p className="fine">{j.career_track}</p>
            {j.discovery_screen && (
              <p className="notice">
                {j.discovery_screen.age_days == null
                  ? "Posting date unknown"
                  : `Posted ${j.discovery_screen.age_days} day(s) ago`}{" "}
                · {j.discovery_screen.count_note}
                <br />
                {j.discovery_screen.reason}
              </p>
            )}
            <p className="fine">
              {j.location_note} {j.country_evidence}
            </p>
            <p className="fine">{j.foreign_applicant_evidence}</p>
            <p className="excerpt">
              {j.description || "Read the original job for full requirements."}
            </p>
            {j.fit && (
              <details>
                <summary>Fit {j.fit.score}/100 · review requirements</summary>
                <Fit value={j.fit} />
              </details>
            )}
            <div className="actions">
              <a
                className="btn secondary small"
                href={j.url}
                target="_blank"
                rel="noreferrer"
              >
                Original posting ↗
              </a>
              <button
                className="btn primary small"
                disabled={c.busy}
                onClick={() =>
                  c.action(
                    () => save(j),
                    "Job saved as unverified for your review.",
                  )
                }
              >
                Read full text & save
              </button>
            </div>
          </article>
        ))}
      </div>
      {!result.jobs?.length && (
        <p className="empty">
          No matching vacancies returned. Try another title, region or source,
          or use the browser links. No substitute jobs were created.
        </p>
      )}
    </>
  );
}
function SearchPage(c: Ctx) {
  const [result, setResult] = useState<R | null>(null);
  const [lastQuery, setLastQuery] = useState<R | null>(null);
  const countries = c.data.preferences.countries
    .filter((x: R) => x.enabled)
    .map((x: R) => x.country);
  return (
    <>
      <Heading
        eyebrow="YOUR EXPERIENCE OPENS DOORS"
        title="Find your next opportunity."
        description="Explore related titles, read original postings and decide what fits your career."
      />
      <form
        className="panel pad stack"
        onSubmit={(e) => {
          e.preventDefault();
          const d = form(e);
          const query = {
            ...d,
            include_unknown_country: d.include_unknown_country === "on",
            include_stretch: d.include_stretch === "on",
            offset: 0,
            limit: 50,
          };
          setLastQuery(query);
          void c.action(
            async () => setResult(await api("search", query, "POST")),
            "Search completed. Check source coverage and any errors below.",
          );
        }}
      >
        <div className="grid">
          <label>
            Job title
            <input
              name="title"
              required
              minLength={2}
              maxLength={160}
              list="target-titles"
              defaultValue={
                typeof window === "undefined"
                  ? ""
                  : new URLSearchParams(location.search).get("title") ||
                    c.data.preferences.target_titles[0] ||
                    "Civil Engineer"
              }
            />
            <datalist id="target-titles">
              {c.data.roles.map((r: R) => (
                <option key={r.title}>{r.title}</option>
              ))}
            </datalist>
          </label>
          <Select
            name="country"
            label="Country"
            value={countries[0]}
            options={countries}
          />
          <Field name="region" label="City / province (optional)" />
          <Select
            name="track"
            label="Career track"
            value={
              typeof window === "undefined"
                ? "civil"
                : new URLSearchParams(location.search).get("track") || "civil"
            }
            options={["civil", "analytics", "combined"]}
          />
          <Select
            name="scope"
            label="Title coverage"
            value="related"
            options={["related", "domain", "exact"]}
          />
          <Select
            name="region_mode"
            label="City / province behaviour"
            value="prefer"
            options={["prefer", "only"]}
          />
          <Select
            name="source"
            label="Search source"
            value="feeds"
            options={["feeds", "usajobs"]}
          />
        </div>
        <div className="grid">
          <Check
            name="include_unknown_country"
            label="Also show postings whose country needs manual confirmation"
          />
          <Check
            name="include_stretch"
            label="Include senior-title stretch opportunities for manual review"
          />
        </div>
        <p className="fine">
          Related searches include title variants within the role family. Domain
          searches cover all supported civil/infrastructure directions in the
          USA and UAE. All US states are in scope; Dubai and Abu Dhabi are the
          preferred UAE locations. Employer sponsorship and permit compatibility
          require posting-specific evidence.
        </p>
        <div className="actions">
          <button className="btn primary" disabled={c.busy}>
            {c.busy ? "Searching…" : "Search opportunities"}
          </button>
          <Link href="/sources">Manage sources →</Link>
        </div>
        <p className="notice">
          Screening: normally ≤{c.data.preferences.max_job_age_days ?? 5} days
          old; counts above {c.data.preferences.max_applicant_count ?? 100}{" "}
          excluded; older jobs require a reported count below{" "}
          {c.data.preferences.older_job_applicant_threshold ?? 20}. Unknown
          counts are{" "}
          {(c.data.preferences.include_unknown_applicant_count ?? true)
            ? "allowed for fresh postings and labelled unknown"
            : "excluded"}
          . <Link href="/preferences">Change these rules →</Link>
        </p>
        <p className="fine">
          Search uses the title and location only. Your private profile stays on
          this computer. Board coverage is limited; availability and eligibility
          require your review.
        </p>
      </form>
      {result && (
        <>
          <Results result={result} c={c} />
          {result.has_more && lastQuery && (
            <button
              className="btn secondary"
              disabled={c.busy}
              onClick={() =>
                c.action(async () => {
                  const next = await api(
                    "search",
                    { ...lastQuery, offset: result.next_offset },
                    "POST",
                  );
                  setResult({ ...next, jobs: [...result.jobs, ...next.jobs] });
                }, "Next result page loaded.")
              }
            >
              Load more live postings ({result.jobs.length} / {result.total})
            </button>
          )}
          {result.employer_targets && (
            <EmployerDirectory
              catalog={{
                ...c.data.sources.catalog,
                employers: result.employer_targets,
                default_country: lastQuery?.country,
              }}
              preferences={c.data.preferences}
              busy={c.busy}
              action={c.action}
              compact
            />
          )}
        </>
      )}
      <Capture {...c} />
      <section className="panel pad">
        <h2>Saved searches</h2>
        <p className="muted">
          Run on demand in batches of up to three queries. Automatic schedules
          are disabled.
        </p>
        <details>
          <summary>Create a saved search</summary>
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              const d = form(e),
                lines = (k: string) =>
                  String(d[k])
                    .split("\n")
                    .map((x) => x.trim())
                    .filter(Boolean);
              void c.action(() =>
                api(
                  "saved-searches",
                  {
                    name: d.name,
                    titles: lines("titles"),
                    countries: lines("countries"),
                    sources: lines("sources"),
                  },
                  "POST",
                ),
              );
            }}
          >
            <Field name="name" label="Search name" required />
            <div className="grid">
              <Field
                name="titles"
                label="Job titles (one per line)"
                value={c.data.preferences.target_titles.slice(0, 3).join("\n")}
                type="textarea"
              />
              <Field
                name="countries"
                label="Countries (one per line)"
                value={countries.slice(0, 2).join("\n")}
                type="textarea"
              />
              <Field
                name="sources"
                label="Sources (one per line: feeds, usajobs)"
                value="feeds"
                type="textarea"
              />
            </div>
            <button className="btn primary" disabled={c.busy}>
              Save search
            </button>
          </form>
        </details>
        {c.data["saved-searches"].map((s: R) => (
          <article className="country" key={s.id}>
            <div className="section-heading">
              <div>
                <h3>{s.name}</h3>
                <p>
                  {s.titles.join(", ")} · {s.countries.join(", ")}
                </p>
                <small>Last run {date(s.last_run)}</small>
              </div>
              <div className="actions">
                <button
                  className="btn secondary small"
                  disabled={c.busy}
                  onClick={() =>
                    c.action(async () => {
                      const r = await api(
                        "saved-searches/" + s.id + "/run?offset=0",
                        {},
                        "POST",
                      );
                      setResult(r.result);
                    }, "Saved search batch completed.")
                  }
                >
                  Run first batch
                </button>
                {s.result?.next_offset != null && (
                  <button
                    className="btn secondary small"
                    disabled={c.busy}
                    onClick={() =>
                      c.action(async () => {
                        const r = await api(
                          "saved-searches/" +
                            s.id +
                            "/run?offset=" +
                            s.result.next_offset,
                          {},
                          "POST",
                        );
                        setResult(r.result);
                      })
                    }
                  >
                    Next batch
                  </button>
                )}
                <button
                  className="btn secondary small"
                  onClick={() =>
                    c.action(() =>
                      api("saved-searches/" + s.id, undefined, "DELETE"),
                    )
                  }
                >
                  Remove
                </button>
              </div>
            </div>
          </article>
        ))}
      </section>
    </>
  );
}
function ApplicationPage(c: Ctx & { a: R }) {
  const a = c.a,
    j = a.job;
  const [verified, setVerified] = useState(j.verification === "verified");
  useEffect(() => setVerified(j.verification === "verified"), [j.verification]);
  const [stage, setStage] = useState(a.stage),
    [approval, setApproval] = useState(false),
    [edit, setEdit] = useState(false),
    [country, setCountry] = useState(
      c.data.preferences.countries.find((x: R) => x.country === j.country)
        ?.template ||
        j.country ||
        "USA",
    ),
    [contact, setContact] = useState("");
  useEffect(() => setStage(a.stage), [a.stage]);
  const active = a.documents.filter((d: R) => d.status !== "superseded");
  return (
    <>
      <Link href="/applications" className="back">
        ← All applications
      </Link>
      <Heading
        eyebrow={j.is_demo ? "FICTIONAL EXAMPLE · NOT AN OPENING" : j.employer}
        title={j.title}
        description={`${j.location} · ${j.country} · Saved ${date(a.created_at)}`}
      >
        <Badge value={a.stage} />
      </Heading>
      {j.is_demo && (
        <p className="warning">
          Fictional demonstration vacancy. It cannot be verified, approved or
          submitted.
        </p>
      )}
      <div className="columns">
        <div>
          <section className="panel pad stack">
            <div className="section-heading">
              <h2>Original vacancy</h2>
              <Badge value={j.verification} />
            </div>
            <p>
              <b>Published pay:</b> {pay(j)}
            </p>
            {j.url && (
              <a href={j.url} target="_blank" rel="noreferrer">
                Read original posting ↗
              </a>
            )}
            <details>
              <summary>Complete saved description</summary>
              <p className="prewrap">
                {j.description ||
                  "No text saved. Add the full description to improve fit checks."}
              </p>
            </details>
            <label className="check">
              <input
                type="checkbox"
                checked={verified}
                disabled={
                  c.busy ||
                  j.is_demo ||
                  ["Approved", "Submitted", "Interview", "Offer"].includes(
                    a.stage,
                  )
                }
                onChange={(e) => {
                  const next = e.target.checked;
                  setVerified(next);
                  void c.action(async () => {
                    try {
                      await api(
                        "applications/" + a.id + "/verification",
                        { confirmed: next },
                        "PUT",
                      );
                    } catch (error) {
                      setVerified(!next);
                      throw error;
                    }
                  });
                }}
              />
              I checked this opening on the original employer source
            </label>
            <button
              className="btn secondary small"
              disabled={!!a.submitted_at || a.stage === "Approved" || j.is_demo}
              onClick={() => setEdit(!edit)}
            >
              {edit ? "Close editor" : "Edit saved job"}
            </button>
            {edit && (
              <form
                className="stack"
                onSubmit={(e) => {
                  e.preventDefault();
                  void c.action(async () => {
                    await api(
                      "applications/" + a.id + "/job",
                      jobBody(form(e)),
                      "PUT",
                    );
                    setEdit(false);
                  }, "Job updated. Verify its source again and regenerate any drafts.");
                }}
              >
                <JobFields job={j} />
                <button className="btn primary" disabled={c.busy}>
                  Save updated vacancy
                </button>
              </form>
            )}
          </section>
          <section className="panel pad">
            <h2>Fit & eligibility review</h2>
            <Fit value={a.fit} />
          </section>
          <section className="panel pad stack">
            <h2>Resume & cover letter</h2>
            <p className="muted">
              One-page ATS-friendly drafts from confirmed, resume-allowed facts.
              Check every line before use.
            </p>
            <div className="grid">
              <label>
                Country template
                <select
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                >
                  {COUNTRIES.map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
              <label>
                Cover-letter contact
                <select
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                >
                  <option value="">Dear Hiring Manager</option>
                  {a.employer.contacts.map((x: R, i: number) => (
                    <option
                      key={i}
                      value={i}
                      disabled={!x.verified || !x.salutation}
                    >
                      {x.salutation || x.name}{" "}
                      {!x.verified ? "(unverified)" : ""}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="actions">
              {["resume", "cover_letter"].map((kind) => (
                <button
                  className="btn secondary"
                  key={kind}
                  disabled={
                    c.busy ||
                    j.is_demo ||
                    ["Approved", "Submitted", "Interview", "Offer"].includes(
                      a.stage,
                    )
                  }
                  onClick={() =>
                    c.action(
                      () =>
                        api(
                          "applications/" + a.id + "/documents",
                          {
                            kind,
                            country,
                            contact_index:
                              contact === "" ? null : Number(contact),
                          },
                          "POST",
                        ),
                      "Draft generated. Review its text and provenance before approving.",
                    )
                  }
                >
                  Generate {kind === "resume" ? "resume" : "cover letter"}
                </button>
              ))}
            </div>
            {!active.length && (
              <p className="empty">
                Your tailored resume and cover letter will appear here.
              </p>
            )}
            {a.documents.map((d: R) => (
              <details
                className="document"
                key={d.id}
                open={d.status === "generated"}
              >
                <summary>
                  {d.kind === "resume" ? "Resume" : "Cover letter"} ·{" "}
                  {d.country_template} · {d.status} · {date(d.created_at)}
                </summary>
                <p className={d.checks.passed ? "success" : "error"}>
                  {d.checks.passed
                    ? "Source claims checked against your current verified profile."
                    : "Claims failed or changed. Generate a fresh draft."}
                </p>
                <pre className="draft">{d.content}</pre>
                <details>
                  <summary>Claim provenance and conversion</summary>
                  <p>PDF workflow: {d.conversion}</p>
                  <pre className="json">
                    {JSON.stringify(
                      { claims: d.claims, checks: d.checks },
                      null,
                      2,
                    )}
                  </pre>
                </details>
                <div className="actions">
                  {["docx", "pdf", "txt"].map((f) => (
                    <a
                      key={f}
                      className="btn secondary small"
                      href={"/api/documents/" + d.id + "/download/" + f}
                    >
                      Download {f.toUpperCase()}
                    </a>
                  ))}
                  <button
                    className="btn primary small"
                    disabled={
                      c.busy || d.status !== "generated" || !d.checks.passed
                    }
                    onClick={() =>
                      c.action(
                        () => api("documents/" + d.id + "/approve", {}, "POST"),
                        "Draft explicitly approved. Nothing was sent.",
                      )
                    }
                  >
                    I reviewed and approve this draft
                  </button>
                </div>
              </details>
            ))}
          </section>
          <section className="panel pad">
            <h2>Notes & employer responses</h2>
            <form
              className="stack"
              onSubmit={(e) => {
                e.preventDefault();
                const el = e.currentTarget;
                void c.action(async () => {
                  await api("applications/" + a.id + "/notes", form(e), "POST");
                  el.reset();
                });
              }}
            >
              <Select
                name="kind"
                label="Record type"
                value="note"
                options={["note", "employer_response"]}
              />
              <Field
                name="body"
                label="Private note / response"
                type="textarea"
                required
              />
              <button className="btn secondary" disabled={c.busy}>
                Save note
              </button>
            </form>
            {a.notes.map((n: R) => (
              <article className="country" key={n.id}>
                <small>
                  {n.kind.replace("_", " ")} · {date(n.created_at)}
                </small>
                <p className="prewrap">{n.body}</p>
              </article>
            ))}
          </section>
        </div>
        <aside>
          <section className="panel pad stack">
            <h2>Your next step</h2>
            <label>
              Application stage
              <select
                value={stage}
                onChange={(e) => {
                  setStage(e.target.value);
                  setApproval(false);
                }}
              >
                {STAGES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            {stage === "Approved" && (
              <label className="check">
                <input
                  type="checkbox"
                  checked={approval}
                  onChange={(e) => setApproval(e.target.checked)}
                />
                I reviewed the original vacancy and current documents, and
                explicitly approve preparing a manual submission
              </label>
            )}
            <form
              className="stack"
              onSubmit={(e) => {
                e.preventDefault();
                const d = form(e);
                void c.action(
                  () =>
                    api(
                      "applications/" + a.id + "/stage",
                      {
                        stage,
                        version: a.version,
                        approval,
                        evidence: d.evidence || "",
                      },
                      "PUT",
                    ),
                  "Stage updated locally. No application or correspondence was sent.",
                );
              }}
            >
              {stage === "Submitted" && (
                <Field
                  name="evidence"
                  label="Evidence of the manual submission (required)"
                  type="textarea"
                  required
                />
              )}
              <button
                className="btn primary"
                disabled={
                  c.busy ||
                  stage === a.stage ||
                  (stage === "Approved" && !approval)
                }
              >
                Save stage
              </button>
            </form>
            <p className="fine">
              To record submission: Draft Ready → explicitly Approved → manually
              apply on the employer's site → record evidence here.
            </p>
            {a.submitted_at && (
              <p className="notice">
                Submission recorded {date(a.submitted_at)}
                <br />
                {a.evidence}
              </p>
            )}
          </section>
          <section className="panel pad stack">
            <h2>Submission evidence</h2>
            <p className="fine">
              Private PNG, JPEG, PDF, TXT or EML, up to 5 MB. Files are
              downloaded, never embedded.
            </p>
            <label>
              Upload confirmation
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.pdf,.txt,.eml"
                disabled={c.busy}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  void c.action(async () => {
                    if (f.size > 5000000)
                      throw new Error("File must be 5 MB or smaller.");
                    const bytes = new Uint8Array(await f.arrayBuffer());
                    let b = "";
                    for (let i = 0; i < bytes.length; i += 8192)
                      b += String.fromCharCode(...bytes.subarray(i, i + 8192));
                    await api(
                      "applications/" + a.id + "/evidence",
                      {
                        filename: f.name,
                        media_type:
                          f.type ||
                          (/\.eml$/i.test(f.name)
                            ? "message/rfc822"
                            : "text/plain"),
                        data: btoa(b),
                      },
                      "POST",
                    );
                  });
                }}
              />
            </label>
            {a.evidence_files.map((f: R) => (
              <a key={f.id} href={"/api/evidence/" + f.id + "/download"}>
                {f.filename} ↓
              </a>
            ))}
          </section>
          <section className="panel pad">
            <h2>Follow-up reminders</h2>
            {a.reminders.map((r: R) => (
              <p key={r.id}>
                {r.title}
                <br />
                <small>
                  {date(r.due_at)} · {r.completed ? "Completed" : "Pending"}
                </small>
                {!r.completed && (
                  <button
                    className="btn secondary small"
                    onClick={() =>
                      c.action(() =>
                        api("reminders/" + r.id + "/complete", {}, "POST"),
                      )
                    }
                  >
                    Complete
                  </button>
                )}
              </p>
            ))}
            {!a.reminders.length && (
              <p className="muted">
                Created 7 and 14 days after recorded submission.
              </p>
            )}
          </section>
          <section className="panel pad">
            <h2>Activity history</h2>
            {a.activity.map((x: R) => (
              <p className="activity" key={x.id}>
                {x.message}
                <small>{date(x.created_at)}</small>
              </p>
            ))}
          </section>
        </aside>
      </div>
    </>
  );
}
