# CareerPilot

A private career workspace that runs on your computer and opens in your browser. It uses your verified facts to explore related engineering roles, compare job requirements, prepare checked one-page drafts and track applications you submit yourself.

**No deployment, Docker, paid API key or hosted database is needed.** Internet access is needed for the first dependency installation and live job searches. Your profile, application records, keys and generated documents stay in the local `data/` folder. CareerPilot does not send applications, email employers or bypass access controls.

## Download and start

The recovery implementation is on the [`careerpilot-recovery` branch](https://github.com/Ackrad-Data-Analyst/Job-App/tree/careerpilot-recovery). [Download its source ZIP](https://github.com/Ackrad-Data-Analyst/Job-App/archive/refs/heads/careerpilot-recovery.zip), then **extract the entire ZIP**. Do not run files inside the ZIP viewer.

1. Install [Python 3.12 or newer](https://www.python.org/downloads/) and [Node.js 24 LTS](https://nodejs.org/) if needed. On Windows, enable **Add Python to PATH** in the Python installer. Close and reopen Explorer or Terminal after installation.
2. On Windows, double-click **start.bat**. On macOS, open **start.command** (or run `bash start.sh` in Terminal). On Linux, run `bash start.sh`.
3. Keep the Start window open. The first start downloads locked dependencies and builds the app; later starts reuse them. The browser opens automatically at `http://127.0.0.1:3000` (or another available local port).
4. Use the matching **stop.bat / stop.command / stop.sh**, or press **Ctrl+C** in the Start window, when finished.

No administrator access is required. Do not bypass operating-system security warnings blindly: inspect the source and launch from a terminal if your system blocks downloaded scripts.

Your database is preserved across restarts. To back up your records, stop the app and privately copy the entire `data/` folder. Keep that folder when updating source files. Do not overwrite it with another person's data.

The public source archive starts with a blank profile. A privately supplied personal package may include `data/private/profile.seed.json`; it is imported only into an empty profile. Alternatively, paste a private JSON seed or recovery code in **Career profile → Import a private profile**. Existing populated profiles are never silently replaced. Review all imported facts before using documents.

## What works

- Responsive green dashboard, verified career profile, role explorer, country priorities and authorisation notes.
- Concrete profile tables for experience, education, skills, projects, certifications, languages, private identity facts and exclusions. Facts have confirmed / unverified / excluded status, learning flags, resume permission and private notes.
- Manual job-description and URL capture; source authenticity remains unverified until you check it yourself.
- Public SmartRecruiters, Greenhouse, Lever and Ashby boards; on-demand saved searches; optional Remotive, Adzuna and USAJOBS integrations. No fabricated fallback results.
- Local, explainable required/preferred skill matching with confirmed, learning and missing skills; seniority, licensing, language and authorisation cautions. Scores are a keyword rubric, not legal eligibility or a hiring prediction.
- Published salary fields and optional country minimums. Unknown salary remains unknown. Cross-currency comparisons require your own dated rates. Monthly/hourly pay is not guessed into an annual salary.
- Table and kanban tracking through Discovered, Under Review, Shortlisted, Draft Ready, Approved, Submitted, Interview, Offer, Rejected and Withdrawn; notes, manually recorded employer responses, CSV export, evidence files and 7/14-day local reminders.
- Employer research and owner-verified public contacts. No guessed emails or external correspondence.
- Extractive resume and short cover-letter drafts, country templates, DOCX/PDF/TXT downloads, per-line provenance, current-fact rechecks and explicit draft approval.

**Search coverage is limited.** Employer feeds cover only configured boards (first 100 SmartRecruiters results per title/country query; first 1,000 for other boards). Some location text may not identify a country; those results can be omitted. Browser links support broader searches on official sites and job boards. Source outages and missing keys appear as errors. A source listing is not an authenticity guarantee; always check the original employer page.

Starter employer-board metadata was checked on 16 October 2026. No live vacancies are preloaded. Recheck boards in Job sources. A live AECOM read could not be verified from the recovery cloud environment; provider parsing and failure behaviour are covered with isolated fixtures. Availability on your computer depends on the provider and your network.

## Document and approval rules

Only confirmed, resume-allowed facts may support a draft. Learning is never counted as an already-held skill. Unknown employment start dates stay blank; an end date is explicitly labelled as an end date. No accomplishments or numbers are invented. MCA, GPA/CGPA, immigration, relocation and work-authorisation statements are blocked. Resume languages are off by default; nationality is limited to the UAE template. Canadian location requires a confirmed fact and explicit preference.

Templates cover Canada, UAE, USA, Australia, United Kingdom, Ireland, New Zealand, Qatar and Italy. They use one column, text-based content, country page sizes, date formatting and supported spelling substitutions. Resume detail is selected from whole confirmed bullets using job keywords. This is local extractive drafting; advanced OpenAI generation is deliberately disabled. There is no claim of expert human tailoring or exhaustive country legal compliance.

PDF conversion tries Microsoft Word through docx2pdf on Windows/macOS, then LibreOffice if installed, then a text-based ReportLab fallback. The PDF must be exactly one page or generation fails with instructions to shorten facts. The conversion method is visible. DOCX rendering can vary by word processor; visually review the exported DOCX before use.

Approval requires **Draft Ready**, your source-verification checkbox and an explicit approval checkbox. Every current generated draft must also be approved and pass current-source checks. You then apply yourself on the employer's website. **Submitted** records that completed manual action and requires evidence; CareerPilot does not perform it. Employer responses are entered manually. Scheduled searches, mailbox access, advanced AI and automatic submissions are not enabled.

## Fictional examples

Run `python start.py --demo` (macOS/Linux: `python3 start.py --demo`) to add three clearly fictional example applications. Select **Fictional examples** in the tracker to see them. They cannot be verified, approved, drafted or submitted. This does not invent facts in your career profile. The public `examples/profile.example.json` is fictional and optional; never use it as your own qualifications.

## Optional private configuration

The launcher creates `data/private/.env` with random local API and session keys. Optional variables are documented in [.env.example](.env.example). Add provider keys there and restart. Never put keys in `NEXT_PUBLIC_*` variables or commit `.env` files.

SQLite is the local default. For a future private PostgreSQL/Supabase instance, set a direct server-side `DATABASE_URL=postgresql+psycopg://...` with TLS, then restart to apply Alembic migrations. Use a database role that can run the migrations and access the private tables. No anonymous browser Supabase API is used. PostgreSQL migrations enable row-level security and revoke public/anon/authenticated table access; configure a separate privileged server role appropriately. Hosted deployment, authentication for public access, storage policies and migrating existing SQLite records require additional work. PostgreSQL is not required or assumed tested for local operation.

Security boundaries: both services bind to loopback; private APIs require a server token; a one-use five-minute browser unlock creates an eight-hour HttpOnly SameSite cookie; mutations require the configured origin. Do not expose these ports to a LAN or the internet. The app does not encrypt your disk: protect your computer account and private backups.

## Development and tests

Requirements: Python 3.12+, Node.js 22.13+ (24 LTS recommended), and [uv](https://docs.astral.sh/uv/) for development. The normal launcher installs uv in a local bootstrap environment if it is missing.

```bash
npm ci
uv sync --frozen --project apps/api
npm run typecheck
npm test
cd apps/api
uv run --frozen pytest -q
uv run --frozen ruff check careerpilot tests alembic
cd ../..
npm run build
# Install Chromium once on a development machine, unless /usr/bin/chromium is available:
npx playwright install chromium
npm run e2e --workspace apps/web
python3 start.py --smoke-test
```

Browser tests start isolated production web/API processes with fictional temporary data, test both desktop and mobile, and do not read your profile. Python tests use isolated databases and mocked provider responses. `--smoke-test` starts the real app, checks readiness and private unlock, then stops its own services. It may initialise your normal local database; use `CAREERPILOT_DATA_DIR=/private/test/path` for an isolated smoke test. `--repair` reinstalls locked dependencies and rebuilds while preserving your records.

To develop with hot reload, use your private environment values for the backend and frontend, including `API_BASE_URL`, `APP_ORIGIN`, `API_TOKEN`, `SESSION_SECRET`, a new `CAREERPILOT_BOOTSTRAP_CODE`, and an epoch-millisecond `CAREERPILOT_BOOTSTRAP_DEADLINE`. Run `uvicorn careerpilot.main:app --host 127.0.0.1` from `apps/api` and `npm run dev --workspace apps/web`. The normal Start script handles these values automatically.

## Structure

```text
apps/web/                 Next.js, TypeScript, Tailwind and browser tests
apps/api/careerpilot/     FastAPI routes, SQLAlchemy models, rules, documents, sources
apps/api/alembic/         Versioned SQLite/PostgreSQL schema migrations
apps/api/tests/           Isolated API, document and provider tests
scripts/                 Packaging and private-file safeguards
examples/                Fictional profile only
data/                    Ignored local records, keys, outputs and logs
start.* / stop.*          Local launch and stop scripts
```

Background search definitions are persisted independently from the provider adapter. Saved searches run in bounded on-demand batches; a future scheduler can call the same service. OpenAI configuration is reserved server-side but no API call is made in this version.

Source commits are reviewable on the recovery branch; the repository's main branch has not been replaced. Personal profile files and generated documents are excluded from source and release packaging by default.

See [SETUP-VALIDATION.md](SETUP-VALIDATION.md) for the recovery test results and platform limitations.
