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
- Direct employer career-page directory, checked SmartRecruiters/Greenhouse/Lever/Ashby feeds, a robots-respecting public Workday careers adapter, on-demand saved searches and optional official USAJOBS access. Indeed and aggregator discovery are excluded. No fabricated fallback results.
- Local, explainable required/preferred skill matching with confirmed, learning and missing skills; seniority, licensing, language and authorisation cautions. Scores are a keyword rubric, not legal eligibility or a hiring prediction.
- Published salary fields and optional country minimums. Unknown salary remains unknown. Cross-currency comparisons require your own dated rates. Monthly/hourly pay is not guessed into an annual salary.
- Table and kanban tracking through Discovered, Under Review, Shortlisted, Draft Ready, Approved, Submitted, Interview, Offer, Rejected and Withdrawn; notes, manually recorded employer responses, CSV export, evidence files and 7/14-day local reminders.
- Employer research and owner-verified public contacts. No guessed emails or external correspondence.
- Extractive resume and short cover-letter drafts, country templates, DOCX/PDF/TXT downloads, per-line provenance, current-fact rechecks and explicit draft approval.

**Search coverage is limited and reported.** Automatic discovery covers enabled, successfully checked supported employer feeds, with bounded pagination and a five-minute source cache. The wider directory is a separate set of employer career-page targets, not an assertion of live vacancies. Source failures, truncated windows and reasons for filtering are visible. Check original postings; page reachability does not prove authenticity or personal eligibility. See the November expansion notes below.

Starter employer-board metadata was checked on 16 October 2026. No live vacancies are preloaded. Recheck boards in Job sources. A live AECOM read could not be verified from the recovery cloud environment; provider parsing and failure behaviour are covered with isolated fixtures. Availability on your computer depends on the provider and your network.

## Document and approval rules

Only confirmed, resume-allowed facts may support a draft. Learning is never counted as an already-held skill. Unknown employment start dates stay blank; an end date is explicitly labelled as an end date. No accomplishments or numbers are invented. MCA, GPA/CGPA, immigration, relocation and work-authorisation statements are blocked. Resume languages are off by default; nationality is limited to the UAE template. Canadian location requires a confirmed fact and explicit preference.

The active workspace offers USA and UAE resume templates. Legacy templates remain in the back end for historical records. They use one column, text-based content, country page sizes, date formatting and supported spelling substitutions. Resume detail is selected from whole confirmed bullets using job keywords. This is local extractive drafting; advanced OpenAI generation is deliberately disabled. There is no claim of expert human tailoring or exhaustive country legal compliance.

PDF conversion tries Microsoft Word through docx2pdf on Windows/macOS, then LibreOffice if installed, then a text-based ReportLab fallback. The PDF must be exactly one page or generation fails with instructions to shorten facts. The conversion method is visible. DOCX rendering can vary by word processor; visually review the exported DOCX before use.

Approval requires **Draft Ready**, your source-verification checkbox and an explicit approval checkbox. Every current generated draft must also be approved and pass current-source checks. You then apply yourself on the employer's website. **Submitted** records that completed manual action and requires evidence; CareerPilot does not perform it. Employer responses are entered manually. Scheduled searches, mailbox access, advanced AI and automatic submissions are not enabled.

## Fictional examples

Run `python start.py --demo` (macOS/Linux: `python3 start.py --demo`) to add three clearly fictional example applications. Select **Fictional examples** in the tracker to see them. They cannot be verified, approved, drafted or submitted. This does not invent facts in your career profile. The public `examples/profile.example.json` is fictional and optional; never use it as your own qualifications.

## Optional private configuration

The launcher creates `data/private/.env` with random local API and session keys. Optional variables are documented in [.env.example](.env.example). Add provider keys there and restart. Never put keys in `NEXT_PUBLIC_*` variables or commit `.env` files.

SQLite is the local default. For a future private PostgreSQL/Supabase instance, set a direct server-side `DATABASE_URL=postgresql+psycopg://...` with TLS, then restart to apply Alembic migrations. Use a database role that can run the migrations and access the private tables. No anonymous browser Supabase API is used. PostgreSQL migrations enable row-level security and revoke public/anon/authenticated table access; configure a separate privileged server role appropriately. Hosted deployment, authentication for public access, storage policies and migrating existing SQLite records require additional work. PostgreSQL is not required or assumed tested for local operation.

Security boundaries: both services bind to loopback; private APIs require a server token; a one-use five-minute browser unlock creates an eight-hour HttpOnly SameSite cookie; mutations require the configured origin. Do not expose these ports to a LAN or the internet. The app does not encrypt your disk: protect your computer account and private backups.

## Apply the Next.js security patch to an existing copy

Version 16.4.4 is now pinned in the source and lockfile. If an earlier copy reports 16.4.0, stop CareerPilot and open Command Prompt in the extracted app folder. Run:

```bat
npm install --workspace apps/web --save-exact next@16.4.4
start.bat
```

The launcher detects the changed lockfile and rebuilds while preserving `data/`. The framework's “Upgrade now” prompt can copy instructions when no coding agent is installed; that message does not mean the dependency was updated. Use the command above to install the patch directly.

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

## Correct an already populated profile

The ordinary profile importer preserves populated profiles. An explicit correction uses `careerpilot.profile_update`: stop the app first, then run the module from `apps/api` with the private corrected JSON path. It validates the entire input, saves a full SQLite database backup under `data/private/backups/`, and matches existing facts by category/title/organisation so their IDs and application references remain intact. Unmatched existing facts are retained. Owner-entered salary comparisons and optional document preferences are preserved. Unsent drafts are superseded and Approved/Draft Ready applications return to Under Review; completed submission history is retained.

A private standalone updater can be generated with `python3 scripts/build_profile_update.py PRIVATE_JSON PRIVATE_OUTPUT.py`. It finds the installed app in its own directory, the working directory, or the default Windows Downloads location; `--app` selects another folder. It automatically uses the app's existing Python environment. The generated file contains personal information and must never be committed or published. Public source includes only the generic updater and fictional tests.

## November search expansion

The original engine searched a small configured ATS pool, not the whole web. The source directory contains 127 candidate official employer career pages and 149 role titles, including bridge/dam, marine/port, transit and adjacent analytics directions. The active USA/UAE market scope displays 72 relevant employer targets; Canada-only targets and Canadian regional planning labels are hidden. All US states are in scope, with Dubai then Abu Dhabi preferred in the UAE. New installs default to USA and UAE only. Location preferences never change the location on a resume.

Automatic discovery reads checked SmartRecruiters, Greenhouse, Lever and Ashby employer feeds. A Workday adapter can read the public careers-search data used by a linked employer page, subject to robots permission and supported schema checks. This is a public UI search endpoint, not a claim of a documented general-purpose Workday API. There are no logins, CAPTCHA bypasses, hidden applicant-count requests, scraping of restricted LinkedIn pages or automatic applications. Indeed domains are excluded from search, capture and saved-source input. Adzuna and Remotive discovery are disabled. LinkedIn and selected government resources remain optional browser links.

Search reads paginated source windows with bounded parallel requests, then normalises locations, deduplicates and screens results locally. SmartRecruiters/Lever are bounded to ten pages, Workday to 400 public results, and whole-board responses to 5,000 rows. Timeouts retain successful boards and report incomplete coverage. UI pagination exposes matching results beyond the old 100-result cutoff. Exact-title, related-family and whole-domain modes are available, with a separate analytics track. A province/city is a preference unless “only” is selected. Source failures, unestablished countries, page limits and reasons for exclusions are visible.

**Directory entries are not vacancies.** New links are unchecked candidates until the owner requests a live check. A successful check establishes page reachability and can discover supported ATS links; it does not establish current hiring, sponsorship, fair treatment or personal eligibility. Unsupported career sites stay browser targets. Company recruitment practices are not inferred from founders’ or employees’ nationality. Personal employer exclusions are private settings. Official career/curriculum requests in this cloud session returned proxy HTTP 403; live access from the owner's computer must be checked, and no current openings or curriculum verification were invented.

Default discovery screening is at most five days old and at most 100 reported applications. Older jobs require a reported count below 20. Fresh employer jobs with no reported count remain included and labelled unknown. Counts are never invented, apply-click numbers are distinct from completed applications, and update-only timestamps do not masquerade as first posting dates. Unknown original dates are excluded unless a qualifying low count or explicit owner exception applies. These filters affect discovery, not historical application records.

Country pay floors support month/year/hour units. Published monthly and annual rates can be compared using twelve calendar months; work hours, bonuses, salary predictions and take-home taxes are never assumed. Unknown salary stays unknown. Country-specific early-career pay exceptions and internship preferences are explicit controls.

OPT screening flags the relationship between actual job duties and the Business Analytics programme supporting OPT; a prior civil degree alone does not establish it. Work availability is separate from an owner-reported work route. EAD approval, exact validity and future extensions are never inferred from an application. Canadian non-clinical hospital analytics is assessed by occupation/duties rather than blanket exclusion of hospital employers. HEC-RAS supporting use under supervision remains distinct from independent proficiency. All work-authorisation, family and mobility details stay in private settings and out of generated resumes.

For an existing local copy, a pinned standalone update can download a fixed GitHub source revision, verify SHA256, back up the database and overwritten source files privately, apply the migration and optionally apply the owner's supplied profile correction. Failure restores the prior source and SQLite snapshot. The generated personal updater contains private data and must never be committed. It uses the existing app environment; `start.bat` handles the subsequent locked install/build. The updater and migrations were exercised on Linux; native Windows execution still requires real local validation.


The private USA/UAE market updater changes only destination preferences and cancelled planning facts. It preserves owner-edited qualifications, country pay/authorisation settings and application history, and exports the updated local profile seed. It backs up the database before changing records.
