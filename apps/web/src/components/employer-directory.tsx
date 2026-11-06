"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
type R = Record<string, any>;
type Props = {
  catalog: R;
  preferences: R;
  busy: boolean;
  action: (work: () => Promise<unknown>, message?: string) => Promise<void>;
  compact?: boolean;
};
export function EmployerDirectory({
  catalog,
  preferences,
  busy,
  action,
  compact = false,
}: Props) {
  const [country, setCountry] = useState(catalog?.default_country || "USA"),
    [region, setRegion] = useState(""),
    [sector, setSector] = useState(""),
    [query, setQuery] = useState(""),
    [page, setPage] = useState(0),
    [updates, setUpdates] = useState<R>({}),
    [progress, setProgress] = useState(""),
    [running, setRunning] = useState(false);
  const cancel = useRef(false);
  useEffect(
    () => () => {
      cancel.current = true;
    },
    [],
  );
  if (!catalog) return null;
  const employers = (catalog.employers || []).map((e: R) => ({
    ...e,
    ...updates[e.key],
  }));
  const sectors = [
    ...new Set<string>(employers.flatMap((e: R) => e.sectors)),
  ].sort();
  const rows = employers.filter(
    (e: R) =>
      (!country || e.countries.includes(country)) &&
      (!region ||
        e.regions.some((r: string) =>
          r.toLowerCase().includes(region.toLowerCase()),
        )) &&
      (!sector || e.sectors.includes(sector)) &&
      (!query ||
        (e.name + " " + e.sectors.join(" ") + " " + e.regions.join(" "))
          .toLowerCase()
          .includes(query.toLowerCase())),
  );
  const visible = rows.slice(page * 12, page * 12 + 12);
  function reset(work: () => void) {
    work();
    setPage(0);
  }
  async function check(keys: string[]) {
    cancel.current = false;
    setRunning(true);
    let done = 0;
    try {
      for (let i = 0; i < keys.length && !cancel.current; i += 8) {
        setProgress(
          `Checking ${done}/${keys.length} employer pages. Requests can take up to a minute per batch.`,
        );
        const result = await api(
          "sources/catalog/check",
          { keys: keys.slice(i, i + 8) },
          "POST",
        );
        setUpdates((old: R) => ({
          ...old,
          ...Object.fromEntries(result.results.map((r: R) => [r.key, r])),
        }));
        done += result.results.length;
        setProgress(
          `Checked ${done}/${keys.length}. Reachability does not establish a vacancy or sponsorship.`,
        );
      }
    } finally {
      setRunning(false);
    }
  }
  return (
    <section className="panel pad employer-directory">
      <div className="section-heading">
        <div>
          <h2>
            {compact
              ? "Broader employer career-page targets"
              : "Direct employer directory"}
          </h2>
          <p className="muted">
            {employers.length} employer targets ·{" "}
            {catalog.role_titles?.length || 143} role titles · Home-base focus:{" "}
            {preferences.home_base || "Not set"}
          </p>
        </div>
      </div>
      <p className="notice">
        Career pages below are separate from live job results. New links are
        unchecked candidates until a successful page check. A company’s size,
        location or international presence does not prove it will hire or
        sponsor you. Each posting and your permit conditions decide that.
      </p>
      <div className="directory-controls grid">
        <label>
          Employer market
          <select
            value={country}
            onChange={(e) => reset(() => setCountry(e.target.value))}
          >
            <option value="">All primary markets</option>
            {(catalog.markets || ["USA", "UAE"]).map((v: string) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Planning location focus
          <select
            value={region}
            onChange={(e) => reset(() => setRegion(e.target.value))}
          >
            <option value="">Any location</option>
            {[...new Set<string>(employers.flatMap((e: R) => e.regions))]
              .sort()
              .map((v) => (
                <option key={v}>{v}</option>
              ))}
          </select>
        </label>
        <label>
          Industry / domain
          <select
            value={sector}
            onChange={(e) => reset(() => setSector(e.target.value))}
          >
            <option value="">All civil and infrastructure domains</option>
            {sectors.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Employer or domain
          <input
            value={query}
            onChange={(e) => reset(() => setQuery(e.target.value))}
            placeholder="Company, rail, marine, dams, GIS…"
          />
        </label>
      </div>
      <div className="actions wrap">
        <button
          className="btn secondary"
          disabled={busy || !rows.length}
          onClick={() =>
            action(
              () => check(rows.map((r: R) => r.key)),
              "Employer page checks saved. Successfully discovered supported feeds are now available for searching.",
            )
          }
        >
          Check {rows.length} filtered employer pages
        </button>
        {running && (
          <button
            className="btn secondary"
            onClick={() => {
              cancel.current = true;
            }}
          >
            Stop after current batch
          </button>
        )}
        <span className="fine" role="status">
          {progress ||
            "Page checks read bounded public pages and robots policies; no logins, CAPTCHA bypass or submissions."}
        </span>
      </div>
      <p className="fine">
        Filters describe planning targets, not verified office locations or open
        positions. Automatic search covers only successfully checked supported
        employer feeds; other employers remain browser targets.
      </p>
      <div className="cards">
        {visible.map((e: R) => (
          <article className="role-card" key={e.key}>
            <small>
              {e.state.toUpperCase()}{" "}
              {e.checked_at
                ? "· " + new Date(e.checked_at).toLocaleDateString()
                : ""}
            </small>
            <h3>{e.name}</h3>
            <p>{e.sectors.join(" · ")}</p>
            <p>
              Planning focus: {e.regions.join(", ") || e.countries.join(", ")}
            </p>
            <p>{e.message}</p>
            <p className="fine">{e.foreign_applicant_evidence}</p>
            <div className="actions">
              <a
                href={e.final_url || e.careers_url}
                target="_blank"
                rel="noreferrer"
              >
                Employer careers ↗
              </a>
              <a href={e.website} target="_blank" rel="noreferrer">
                Official site ↗
              </a>
              <button
                className="btn secondary small"
                disabled={busy}
                onClick={() =>
                  action(() => check([e.key]), "Employer page check saved.")
                }
              >
                Check this page
              </button>
            </div>
            <details>
              <summary>Source evidence</summary>
              <p>{e.provenance}</p>
              <p className="fine">Requested: {e.careers_url}</p>
              {e.final_url && <p className="fine">Reached: {e.final_url}</p>}
              <p>Supported verified feeds: {e.feed_ids?.length || 0}</p>
            </details>
          </article>
        ))}
      </div>
      <div className="actions">
        <button
          className="btn secondary small"
          disabled={!page}
          onClick={() => setPage(page - 1)}
        >
          Previous employers
        </button>
        <span className="fine">
          {rows.length ? page * 12 + 1 : 0}–
          {Math.min((page + 1) * 12, rows.length)} of {rows.length} career-page
          targets
        </span>
        <button
          className="btn secondary small"
          disabled={(page + 1) * 12 >= rows.length}
          onClick={() => setPage(page + 1)}
        >
          Next employers
        </button>
      </div>
    </section>
  );
}
export function EducationPathways({ catalog }: { catalog: R }) {
  if (!catalog) return null;
  return (
    <section className="panel pad">
      <h2>Civil engineering + business analytics</h2>
      <p className="notice">
        These are directions to investigate. A programme’s coursework is
        academic context; it does not establish that you completed a particular
        module, hold a professional licence or can use a tool independently.
        Matching still uses only your confirmed, resume-allowed facts.
      </p>
      <div className="cards">
        {catalog.education_pathways?.map((p: R) => (
          <article className="role-card" key={p.title}>
            <h3>{p.title}</h3>
            <p>{p.bridge}</p>
            <p>{p.titles.join(" · ")}</p>
            <p>
              <b>Check:</b> {p.check}
            </p>
          </article>
        ))}
      </div>
      <details>
        <summary>Official curriculum sources and verification limits</summary>
        {catalog.curriculum_sources?.map((r: R) => (
          <p key={r.url}>
            <a href={r.url} target="_blank" rel="noreferrer">
              {r.institution}: {r.programme} ↗
            </a>
            <br />
            <small>{r.status}</small>
          </p>
        ))}
      </details>
    </section>
  );
}
