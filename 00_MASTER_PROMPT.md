# IAU AI Platform — Master Prompt for Claude Code

> **This file is the contract that Claude Code MUST READ at the start of every session.**
> Breaking a rule breaks the project. If you cannot follow the rules, stop
> working and ask the user.

---

## 1. PROJECT IDENTITY

- **Project name:** IAU AI Online Course Platform (v3)
- **Goal:** An education platform where students learn AI unit by unit and, at the end
  of each unit, upload Python code that is tested automatically.
- **Stack:** Next.js 16 + Prisma 7 + PostgreSQL 16 + Docker sandbox + Caddy
- **Platform:** Runs on a single host with Docker Compose.
- **Key differences (v2.2 → v3):**
  - NO cooldown (unlimited attempts)
  - NO Redis (an in-memory semaphore is enough, <20 concurrent)
  - NO gVisor (standard Docker + seccomp + cap-drop is enough)
  - Detailed per-test feedback (expected vs actual)
  - Content-as-code (content/units/ folder, discover script)

---

## 2. HARD LIMITS — DO NOT VIOLATE

### 2.1. Directory Ownership (OWNERSHIP BOUNDARIES)

```
iau_platform/
├── app/              ← Owned by CLAUDE CODE. Next.js code goes here.
├── runner/           ← Owned by CLAUDE CODE. Runner service goes here.
├── infra/            ← Owned by CLAUDE CODE. docker-compose, Caddyfile, Makefile, seccomp.json
├── scripts/          ← Owned by CLAUDE CODE. DB scripts, ingest, cleanup
├── docs/             ← Owned by CLAUDE CODE. Technical docs, self-test MDs
│
├── content/          ← Owned by DENIZ. CLAUDE CODE DOES NOT TOUCH IT.
│   ├── inbox/        ← Deniz's delivery gate — new content is dropped here
│   └── units/        ← Active unit content — placed by the ingest script
│
├── .env              ← Owned by DENIZ. Claude Code may only write .env.example.
└── .env.example      ← CLAUDE CODE may write
```

**RULE:** Claude Code never writes to the `content/` directory, the `.env` file, or
this file itself (`00_MASTER_PROMPT.md`). Only Deniz may change these
files.

If Claude Code needs to create a new directory, it asks first. After creating it,
it tells Deniz the line to add to §2.1 of this document.

### 2.2. Phase Discipline

Claude Code works on **ONE PHASE** at any given time (see 01_BUILD_PLAN.md).
- Do not move to the next phase before the current one is complete.
- Sub-tasks within a phase are done in order. No sub-task is skipped.
- After each sub-task, wait for Deniz's approval.
- Do not move to the next sub-task without approval.

### 2.3. Test-First Rule

- Every new code file comes with a self-check that tests it:
  - A manual command (e.g. `docker compose exec app npm run check:auth`)
  - Or an automated test (Jest, Vitest, pytest)
- Non-working code is not committed. Code containing "TODO" is not committed.

### 2.4. Security Constants (compliance with the SECURITY PROTOCOL)

- NO hardcoded secrets. Everything goes through `process.env.XXX`.
- NO SQL string concatenation. Prisma ORM is used.
- Password hashing: bcrypt cost 12. md5/sha1 strictly forbidden.
- User input: validate + sanitize. Zod schemas are used.
- NO CORS wildcard. Whitelist.
- Debug=false in production. Stack traces are never shown to the user.
- Every endpoint is protected by auth middleware (except public ones, via an explicit whitelist).
- Sandbox: `--network=none`, `--read-only`, `--cap-drop=ALL`,
  `--security-opt=no-new-privileges`, `--security-opt=seccomp=<profile>`,
  `--pids-limit=64`, memory 512MB, CPU 0.5, timeout 10s.
- Rate limiting on all public endpoints (in-memory, sliding window).
- Zod input validation on every endpoint.
- For uploaded ZIPs: size limit, decompressed size limit, file count limit,
  allowed extensions whitelist, path traversal check.

### 2.5. Development Discipline

- The main branch (`main`) must always be in a working state.
- New feature → new branch (`feat/<name>`). No merge without tests + approval.
- Every commit message follows the Conventional Commits format:
  - `feat(auth): add JWT refresh flow`
  - `fix(runner): handle zip bomb edge case`
  - `docs(architecture): add runner flow diagram`
- **Push to GitHub after every approved sub-task, not at the end of the project** (see §9 GitHub Push Protocol).
- README.md is minimal at project start and reaches portfolio quality at the end of Phase 7.

### 2.6. No Personal Information

- Personal information is NOT USED in code, tests, seed data, or docs.
- Mock data: generic, e.g. `test+1@example.com`, `Alice Example`, etc.
- Partner/collaborator names and users' private information never go into docs or code.

---

## 3. OUTPUT FORMAT — HOW YOU DELIVER TO DENIZ

When Claude Code finishes a sub-task, it reports. But **every sub-task falls into one of two
classes**, and the behavior differs accordingly:

### 3.A. AUTO-VERIFIABLE SUB-TASK (the majority)

If the sub-task can be verified by command output alone (build success, unit test pass,
health check, grep result, docker compose up OK), **do not bother** Deniz:

1. Run the self-test commands.
2. If all PASS:
   - Commit (conventional)
   - Push (§9 GitHub Push Protocol)
   - Give a short report (format below)
   - **Immediately move to the next sub-task and start working**
3. If any self-test FAILS:
   - Stop. Tell Deniz the error and what you tried.
   - Do not retry more than 3 times.

**Short report format (auto-continue case):**

```
✅ Sub-task X.Y: <title> completed.

Done: <1-2 lines>
Changed files: <list>
Self-test: unit PASS (12/12) · build OK · secret grep CLEAN
Commit: feat(auth): add JWT signing helper → pushed to origin/feat/<n>

▶️ Sub-task X.Y+1: <title> starting.
```

### 3.B. SUB-TASK REQUIRING MANUAL TESTING (pause)

If completing the sub-task requires Deniz to click in the browser, visually
check the UI, or make a subjective judgment: **STOP**. Give a long report:

```
✋ Sub-task X.Y: <title> — waiting for Deniz's test.

### Done
- <bullet>

### Changed files
- <list>

### Automated self-test results
- [x] unit test: PASS (12/12)
- [x] build: OK
- [x] security grep: CLEAN

### Why manual testing is needed
<UI flow, subjective judgment, etc.>

### Test instructions for Deniz
1. `docker compose up -d`
2. In the browser: `http://localhost/register`
3. Create a test account: `demo@test.com` / `Test1234!`
4. Expected: 200 OK, redirect to /login

### Done automatically after approval
- git commit + push origin/feat/<n>
- Sub-task X.Y+1 (<title>) will start
```

When Deniz writes "onay" or "geç" ("approve" / "skip ahead"):
1. Commit + push.
2. Send a single line: "Sub-task X.Y approved, pushed. Moving on to the next one: X.Y+1."
3. Start the next sub-task **without stopping**.

### 3.C. HOW TO DECIDE WHICH ONE IT IS

Decision matrix — a sub-task is NOT auto-verifiable if:
- The UI render result needs a visual check
- It needs a subjective "does it look good" judgment
- It requires manual clicking in the browser
- It is an end-to-end user flow (register → login → submit → result)
- The content needs Deniz's subjective approval (README wording, etc.)

When in doubt, choose 3.B (more conservative). But don't stop needlessly —
if the build and test commands returned PASS, there is no need to ask for approval.

---

## 4. CONTENT DELIVERY — WHAT DENIZ HANDS OVER AT THE GATE

When Deniz prepares final exams and unit content, they are not handed to Claude Code
directly as code. Instead, a package in a specific format is dropped into the
`content/inbox/` folder. The format is detailed in 02_CONTENT_CONTRACT.md.

Claude Code's job:
1. Have written the `scripts/ingest-content.ts` command (in Phase 3).
2. When Deniz drops `content/inbox/unit-XX.zip`, this script runs and places the content
   in the right location.
3. Claude Code **never** writes anything manually into `content/inbox/`.
4. Claude Code **never** edits files under `content/units/`.
   It only does discovery + DB upsert.

---

## 5. SESSION PROTOCOL

At the start of every Claude Code session:

1. State that you HAVE READ this file (00_MASTER_PROMPT.md).
2. State the current active phase and sub-task from `01_BUILD_PLAN.md`.
3. Focus on that sub-task. Do nothing else.
4. When the sub-task is done:
   - 3.A (auto-verifiable) → run the self-test; if PASS, commit+push+short
     report, **start the next one immediately**. Don't bother Deniz.
   - 3.B (manual test needed) → long report, STOP, wait for approval.
5. When Deniz says "onay"/"geç"/"devam" ("approve"/"skip ahead"/"continue"): commit+push, start the next one.
6. The next sub-task follows the same loop.

**Core rule:** Do NOT STOP after receiving approval. Commit, push, and starting the next
task must be part of the same response.

At the end of every session:

1. Write unfinished work to `docs/WIP.md`.
2. State clearly where the next session should pick up.
3. No uncommitted changes (commit + push at the end of every sub-task).

---

## 6. ANTIPATTERN WARNINGS — DO NOT DO THESE

- ❌ "I'm refactoring across the project" — never. Only the active sub-task.
- ❌ More than one phase at a time. No parallel work.
- ❌ Pushing without waiting for approval on a sub-task that needs manual testing — STOP (see §3.B).
- ❌ Asking for unnecessary approval on an auto-verifiable sub-task — CONTINUE (see §3.A).
- ❌ Writing under `content/`. That belongs to Deniz.
- ❌ "Let me add this too" — scope creep. Only what was asked.
- ❌ "wip", "stuff", "changes" in commit messages. Conventional Commits are mandatory.
- ❌ Features without tests. Every piece of code + a self-test.
- ❌ Putting a secret in code instead of `.env`. Forbidden.
- ❌ Using a user's personal information as seed data. Forbidden.
- ❌ Closing a sub-task without pushing. If it is approved, it must be pushed.

---

## 7. OTHER DOCUMENTS YOU MUST READ

- `01_BUILD_PLAN.md` — Phase and sub-task list
- `02_CONTENT_CONTRACT.md` — Content delivery format
- `docs/ARCHITECTURE.md` — Technical architecture (to be created in Phase 1)
- `docs/WIP.md` — Unfinished work (updated automatically)

---

## 8. RULES FOR COMMUNICATING WITH DENIZ

- If something is unclear, ask. Don't guess.
- If you are stuck on a sub-task after 3 attempts, stop and ask.
- Get approval for big decisions (library choice, schema change, new service).
- If an error occurs, report it openly; don't hide it. "It worked, but..." raises suspicion.
- Reply in Turkish, but keep code/commits/logs in English.

---

## 9. GITHUB PUSH PROTOCOL

Every time a sub-task is completed (auto-approved or after Deniz's approval) it
**must be pushed to GitHub**. Tool: GitHub CLI (`gh`).

### 9.1. First session — repo setup (one time)

At session start, check `git remote -v`:

**If there is no remote:**
1. Check authentication with `gh auth status`.
   - If unauthenticated: STOP, tell Deniz to run `gh auth login`.
2. Ask Deniz (exceptional approval point):
   ```
   No GitHub remote. Shall I create a new private repo?
   Suggested name: iau-ai-platform-v3
   Visibility: private
   ```
3. If approved:
   ```bash
   gh repo create iau-ai-platform-v3 --private --source=. --remote=origin
   git branch -M main
   git push -u origin main
   ```
4. The remote info is written to `docs/WIP.md`.

**If a remote exists:** Skip, go straight to §9.2.

### 9.2. Push loop after every sub-task

Before the sub-task starts:
```bash
git checkout -b feat/<short-name>   # e.g. feat/auth-jwt, feat/sandbox-image
```

When the sub-task is done (automatically or after approval):
```bash
git add -A
git diff --cached --stat   # change summary to the log
git commit -m "<conventional-commit-message>"
git push -u origin feat/<short-name>
```

PR automation to `main` is NOT set up at first. Feature branches are merged into `main`
only when a phase is complete (end of phase = manual merge approval).

### 9.3. End-of-phase merge

When all sub-tasks of a phase are complete:

1. Merge all feat/* branches into `main` in order (squash commit):
   ```bash
   gh pr create --base main --head feat/<name> --title "Phase N.X: <title>" --fill
   gh pr merge --squash --delete-branch
   ```
2. Tag `git tag phase-N-complete` on `main`
3. `git push --tags`

### 9.4. Commit message template

Conventional Commits + sub-task reference:

```
<type>(<scope>): <description>

Task: X.Y — <sub-task title>

<optional description>

Self-test: unit PASS (12/12) · build OK · secret grep CLEAN
```

Example:
```
feat(auth): add JWT signing helper with jose

Task: 5.1 — Auth library (jose + bcrypt)

Implements JWT sign/verify with httpOnly cookies, bcrypt cost 12,
timing-safe password compare.

Self-test: unit PASS (8/8) · build OK · secret grep CLEAN
```

### 9.5. If the push fails

- Network error → retry 3 times (exponential backoff: 2s, 5s, 10s)
- Authentication error → STOP, tell Deniz
- Merge conflict (rare, thanks to branch isolation) → STOP, tell Deniz
- Protected branch push rejected → STOP, switch to the PR flow

### 9.6. .gitignore requirements

Before every push, `.gitignore` must contain:
- `.env`
- `node_modules/`
- `content/inbox/*.zip`
- `content/inbox/processed/`
- `content/inbox/errors/`
- `content/units/*/education.pdf` (large files — LFS or external)
- `*.log`
- `.next/`, `dist/`, `build/`
- `app/public/pdfs/*.pdf` (same reason)

The **structural files** under `content/units/` (`unit.yaml`, `projects.md`,
`tests/test_runner.py`) are included in git — PDF and ZIP content stays out.

### 9.7. Large file strategy

Education PDFs and reference ZIPs are not committed to git. Two options:

1. **Git LFS** (recommended): if Deniz wants it, `git lfs track "*.pdf"` is set up in Phase 1.1
2. **External storage**: PDFs live on S3/CDN, only the URL is kept in the DB

Claude Code asks Deniz about this choice in Phase 1.1 (exceptional approval point).
