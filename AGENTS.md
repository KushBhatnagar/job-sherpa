# Job Sherpa: instructions for coding agents

You are helping one person with their job search. This file is read by Claude
Code (via CLAUDE.md), Codex, Cursor, Gemini CLI, Aider and other agents that
support AGENTS.md. Read it fully before doing anything.

## How the project is split
- **Code** (`sherpa/`, `bin/sherpa`): stores, fetches, checks and renders.
  Standard-library Python, plus Typst for PDFs.
- **Playbooks** (`playbooks/*.md`): the judgment work. Follow the matching one:
  | The user wants to... | Playbook |
  |---|---|
  | get set up, or `me/` is empty | `playbooks/onboard.md` |
  | find or check new jobs (daily routine) | `playbooks/find-jobs.md` |
  | score or triage jobs | `playbooks/score-fit.md` |
  | a resume for a job | `playbooks/tailor-resume.md` |
  | a cover letter | `playbooks/draft-cover-letter.md` |
  | prepare for a screen or interview | `playbooks/prep-interview.md` |
- **The user's data** (`me/`, or wherever `SHERPA_HOME` points): profile,
  bullets, database, drafts, applications. Private and gitignored.

Run commands as `bin/sherpa <command>` (or `python3 -m sherpa <command>`) from
the repo root. `bin/sherpa --help` lists them; `bin/sherpa doctor` checks setup.
The fictional sample user lives in `examples/alex/`; try anything against it
with `SHERPA_HOME=examples/alex`.

## Hard rules (see PRINCIPLES.md for why)
1. **Never invent, inflate or embellish.** Every resume and cover-letter claim
   must trace to a bullet in `me/bullets.yaml`. Rewording for vocabulary is
   fine; changing a number, scope, title or outcome is not. The render step
   checks this; never work around it with `--force`.
2. **Never submit an application** or send anything on the user's behalf.
   Prepare, log and tailor; the user submits.
3. **Never score a job without its full description.** Excerpts hide the
   requirements that matter.
4. **A stated minimum the user doesn't meet caps the fit score** at
   `[search].hard_gate_cap` in `me/profile.toml` (default 6).
5. **Name domain gaps honestly in cover letters, but never restate a numeric
   bar the user falls short of** (years, degree level).
6. **Never scrape** LinkedIn, Naukri, Indeed, Glassdoor or any site whose terms
   forbid automated access. Discovery uses public job-board APIs only; the
   user pastes anything else.
7. **`me/` never leaves the machine.** Don't paste its contents into web
   searches, issues, pull requests or external services, and never commit it.
   If the user asks you to contribute a fix upstream, check the diff has no
   personal data first.
8. **Don't change the user's profile or filters on your own.** Suggest the
   change and let them decide.

## Working style
- Ask before guessing anything about the user. A missing fact stays missing.
- Keep the user's own words in their stories and answers; tidy, don't rewrite.
- Every command that changes data prints what it did; report it plainly.

## Contributing to Job Sherpa itself
Code changes: keep the standard-library-only rule (Typst aside), add or update
a test in `tests/`, and run `python3 -m unittest discover -s tests`. Playbook
changes: keep the hard rules above intact. See CONTRIBUTING.md.
