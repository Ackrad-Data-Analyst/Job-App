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
