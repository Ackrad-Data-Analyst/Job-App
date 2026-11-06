# Recovery validation — 30 October 2026

The previous workspace artifact and source were unavailable. This recovery implementation is committed to `careerpilot-recovery`; `main` is unchanged. The public GitHub branch ZIP was downloaded successfully with HTTP 200 and checked for the launcher and application source. Chat attachment delivery itself cannot be verified from the build machine.

Completed checks:

- 60 isolated Python API, document, provider and approval tests passed.
- 5 local-session unit tests passed.
- 8 production-browser tests passed: dashboard/profile, manual capture, fit, checked resume generation, explicit approval, recorded manual submission, reminders, preferences, source failures and unauthenticated access, on desktop and mobile viewports.
- TypeScript checking, production Next.js build and configured Ruff lint/format checks passed.
- The personal ZIP was extracted into a new folder containing a space. Locked dependencies installed, migrations and private seed import completed, both production services started on loopback, and the one-use browser unlock passed.
- A record saved through the authenticated browser proxy survived Stop and restart; the imported profile remained unchanged. Services stopped cleanly.
- The private profile produced 18 checked drafts across nine country templates, with one-page PDFs. Personal content and generated documents were not printed or committed.
- Both ZIPs passed integrity and content checks. The personal ZIP contains only one additional private seed; neither ZIP contains keys, databases, logs, runtime dependencies or generated documents. Tracked source was scanned for private name/contact values and common credential patterns.

Provider adapters were tested with published-schema fixtures and explicit failure cases. A live AECOM read could not be verified from this recovery cloud network. No live vacancies were preloaded and no substitute vacancies were invented. Recheck boards in Job sources on the local computer.

Native Windows/macOS execution, Microsoft Word automation and PostgreSQL/Supabase execution were not available in this Linux environment. Windows/macOS launchers are included; PDF fallback and SQLite local operation were exercised. Local use requires no hosting or cloud publication.

## 3 November 2026 maintenance check

Next.js and its lockfile were upgraded from 16.4.0 to the offered 16.4.4 security patch. TypeScript checking, the production build, all five session unit tests and all eight desktop/mobile browser tests passed against 16.4.4. The private recovery block was decoded, validated and imported into an isolated empty database: all 71 facts and their restrictions were retained; importing over an existing profile was blocked. No personal records were added to Git.

The profile-correction workflow passed 65 Python tests, including preservation of existing fact IDs, saved applications, submitted history, owner-entered salary settings, repeated application and rejection of invalid corrections before mutation. A generated private standalone updater was also exercised against an isolated existing database: environment bootstrap, complete backup and original backup contents, refusal while the app is running, and successful repeat execution were checked. The latest private correction uses the supplied updated summary plus the owner's subsequent Canadian-work-permit confirmation; it contains no permit or passport numbers. Native Windows execution of the updater remains untested here.


## 5 November 2026 search expansion and local upgrade

The reviewed functional release is commit `1abcec55167bc4af7d44d17efecff7e2e87491a6` on `careerpilot-recovery`. Its full-revision GitHub source ZIP was downloaded and checked against SHA-256 `48f1df3eafa12ce8b6b109a0ccc7e7c5c47e46d498af7bba17768ef12ac7d3cf`.

- 144 Python tests, five session unit tests and 12 production browser tests passed. The browser cases cover desktop and mobile, source-directory filtering, career pathways, search pagination, applicant-count labels and preferences as well as the existing application workflow.
- TypeScript checking, the Next.js 16.4.4 production build and Ruff lint/format checks passed.
- The pinned standalone updater was exercised against an older installed application in a folder containing spaces, using an isolated API environment. It migrated the old database, made source and database backups, preserved existing environment secrets and saved/submitted application history, applied private owner corrections, and retained original fact identifiers. Repeat execution, refusal while running and rollback on failure were tested.
- The upgraded installation completed dependency installation and a production build, started on loopback, unlocked through the browser-cookie flow, served profile/settings/catalogue/search endpoints, stopped, restarted with identical records, and shut down cleanly.
- The latest private profile produced 18 provenance-checked, one-page DOCX/PDF drafts across nine country templates. Expected education dates, supervised software use and document exclusions were checked without printing or committing personal content.

The directory contains 127 candidate official-employer career pages and 149 role titles. Directory entries are targets, not verified vacancies or 127 connected live feeds. New employer pages and university course references could not be independently checked here: this environment's proxy returned HTTP 403 for those external sites. These records remain unchecked, and no hiring, sponsorship or live-vacancy claims are inferred. Run the source checks in the locally installed app; unsupported career sites remain browser links. Provider parsing, pagination, failures and robots restrictions were checked with fixtures. No CAPTCHA bypass, external correspondence or submission automation was added.

Fresh employer jobs with unknown applicant counts are included with an explicit unknown label. Strict posting-age and known completed-application rules are separate from click counts; old jobs require evidence of fewer than 20 applications. No Indeed results are accepted. Owner-specific profile corrections are packaged only in the private download, never in this repository.

Native Windows execution, Microsoft Word automation and PostgreSQL/Supabase execution remain untested in this Linux environment. The updater uses the existing Windows Python installation; the actual upgrade and production lifecycle were tested on Linux. Local use requires no deployment.


## USA/UAE market change — 5 November 2026 (owner's local date)

New installs and visible market/template selectors now focus on USA and UAE. The employer catalogue is scoped to enabled markets and removes irrelevant Canadian region tags; 72 of the 127 source-directory targets remain relevant to these markets. No new vacancy or hiring claims were introduced.

The private market correction removes the cancelled destination, permit and family-mobility planning facts, resets destination preferences, and removes or narrows saved searches for retired markets. It retains owner-edited career facts, USA/UAE pay and authorisation settings, application records and submitted history. Historical project research is not rewritten as a change of travel plan. The local seed is exported from the resulting database, preserving local edits rather than restoring an older profile export.

147 Python tests, five session unit tests and 12 desktop/mobile browser tests passed, along with TypeScript checking, the production build and Ruff source checks. The generated market updater was run twice against an existing installed app: it preserved candidate edits, saved/submitted records and USA/UAE salary settings, removed the cancelled planning facts, and exported the canonical private seed. Native Windows execution remains untested here.
