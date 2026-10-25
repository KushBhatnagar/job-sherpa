# Job Sherpa

**An honest job-search assistant that runs inside your coding agent.**

> A sherpa doesn't climb the mountain for you. They know the route, carry the
> load and stop you from taking a wrong step. Job Sherpa does that for your job
> search; the climb, and every application, stays yours.

Give it your resume and answer a set of questions. It builds a private knowledge
base about you, finds jobs on public company job boards, scores how well each
one fits, tailors resumes and cover letters that **never invent a claim**, and
helps you prepare for the interviews.

Works with Claude Code, Codex, Cursor, Gemini CLI, Aider, or any agent that can
read files and run commands, and the `sherpa` command line also works on its own.

![How Job Sherpa works: your resume and questionnaire answers build a private folder on your computer; from it, Job Sherpa finds jobs, scores the fit, tailors your resume and cover letter, you apply, it tracks and follows up, and helps you prepare for interviews](docs/how-it-works.png)

An example session (illustrative):

```
you:     onboard me. my resume is in me/source/resume.pdf
agent:   (reads it, drafts 24 bullets with their source lines, asks what's missing)
you:     find jobs
agent:   discovered 31 new jobs · 9 scored 7+ · shortlist: me/drafts/application-shortlist-….md
you:     tailor a resume for job 412
agent:   rendered me/drafts/412__…/Your Name_Resume.pdf (1 page) · every claim traced
```

## Everything stays on your computer

- **No server, no account, no sign-up.** Job Sherpa is a folder you clone.
- **Your data lives in one private folder, `me/`:** profile, achievement
  bullets, stories, drafts, and a local SQLite database of jobs and
  applications. It's gitignored, and a git hook refuses to commit it.
- **The only network calls** are to public job-board APIs to fetch postings.
  Nothing about you is sent with them.
- **One caveat:** your coding agent sends the files it reads to its AI model,
  as it does with any code you open in it. If that matters to you, use an
  agent or model you trust with your resume, or run the `sherpa` command line
  on its own.

## Why another AI resume tool?

Because most of them make things up. Job Sherpa is built around a few rules, each with its reasons in
[PRINCIPLES.md](PRINCIPLES.md):

- **Every claim traces to your bullet bank.** Rewording is fine; a new number
  is not. The render step checks every number and refuses what it can't trace.
- **A requirement you don't meet caps the fit score.** Years, degree,
  authorization: recruiters screen on these first, so scoring does too.
- **No scoring from excerpts.** A job with only a snippet waits for its full
  description.
- **Honest about gaps, never self-defeating.** Cover letters name domain gaps
  and never restate a years or degree shortfall.
- **No scraping.** Public job-board APIs (Greenhouse, Lever, Ashby,
  SmartRecruiters, Adzuna); you paste anything from LinkedIn and similar sites.
- **You submit.** It prepares, tracks and reminds; it never applies for you.

## Quick start (about 10 minutes)

Needs Python 3.11+ and git.

```bash
git clone https://github.com/KushBhatnagar/job-sherpa.git
cd job-sherpa
pip install typst                       # PDF rendering (or: brew install typst)
git config core.hooksPath .githooks     # blocks committing your private folder
bin/sherpa init                         # creates me/ (private, gitignored)
```

Put your resume in `me/source/`, open the folder in your coding agent, and say:

> **Onboard me.**

The agent follows [`playbooks/onboard.md`](playbooks/onboard.md): it reads
your resume, drafts your bullet bank, walks you through
[the questionnaire](onboarding/questionnaire.md) one block at a time, and
renders your master resume and cover letter. Then, day to day:

| Say | What happens |
|---|---|
| "Find jobs" | discover → fill in missing descriptions → score → shortlist |
| "Score job 412" / "Add this job: …" | fit score with hard gates, angle and gaps |
| "Tailor a resume for 412" | one-page resume from your bullets, every claim checked |
| "Write a cover letter for 412" | one-page letter, gaps named honestly |
| "I applied to 412" / "412 rejected me" | logged; `sherpa stats` shows your funnel |
| "Prepare me for the 412 interview" | a prep sheet: likely questions matched to your own stories, honest answers to the hard ones, questions to ask, and a mock round |

On Windows, use `python -m sherpa` wherever this README says `bin/sherpa`.
Want `sherpa` on your PATH? Run `pip install -e .` inside the clone.

### Try it without your own data

A fictional sample user, Alex Rivera (backend engineer, Berlin), lives in
`examples/alex/`:

```bash
SHERPA_HOME=examples/alex bin/sherpa master-resume
```

### Without a coding agent

The agent does the judgment (is this job a fit, which bullets to lead with).
Everything mechanical is a plain command you can run yourself:
`bin/sherpa discover`, `inbox`, `show <id>`, `add-job`, `apply`, `applications`, `log`,
`followups`, `stats`, and `master-resume` once your `me/` files are filled in.
See [Commands](#commands).

## How it fits together

- **`sherpa/`**: the CLI. Standard-library Python, no dependencies besides Typst.
- **`playbooks/`**: the judgment, as plain Markdown any agent can follow:
  onboarding, finding jobs, scoring, tailoring, cover letters, interview prep.
  `AGENTS.md` points agents to them; `.claude/skills/` wraps them for Claude Code.
- **`me/`**: everything about you. Gitignored, and the git hook refuses to
  commit it. Point `SHERPA_HOME` elsewhere to keep it outside the repo.
- **`starter-lists/`**: ~100 tech companies with verified job-board tokens,
  copied into `me/companies.yaml` for you to edit.

## Commands

`bin/sherpa --help` lists everything. The ones you'll use most:

| Command | Does |
|---|---|
| `doctor` | checks your setup, says what's missing |
| `discover` | fetches new postings, reports what the filters dropped |
| `add-job --company … --title … --file jd.txt` | adds a job you found yourself |
| `inbox` / `show <id>` | new jobs / one job in full |
| `enrich-jd` | finds full descriptions for excerpt-only jobs |
| `check-companies` | tests every company's job-board entry |
| `shortlist-export` | writes a dated shortlist of your best matches |
| `bullets --tags a,b` | searches your bullet bank |
| `check --data payload.json` | traces a resume/letter to your bullets without rendering |
| `applications` | your applications with their ids and last event |
| `apply`, `log`, `followups`, `stats` | tracking |
| `backup` | copies your database to `SHERPA_BACKUP_DIR` (also weekly, automatically) |

Optional: a free [Adzuna](https://developer.adzuna.com) key in `.env` (see
`.env.example`) adds a keyword search across employers not on your list.

## Is it actually honest? The eval

Two layers of checking:

- **Code guarantees, tested on every change** (`tests/`): an untraceable resume
  line or an invented number blocks the PDF, a missing hard requirement caps the
  score, a job without its full description can't be scored. These hold
  whichever AI model you use.
- **An eval of the agent's judgment** ([`evals/`](evals/)): real, headless
  agent sessions on fictional users and job descriptions built to tempt it:
  a buried 7-year minimum, a job wanting skills the user doesn't have, a vague
  resume line begging for a number. Each output is checked against the rules in
  PRINCIPLES.md.

**Latest results** (Claude Code, 25 Oct 2026, [full report](evals/reports/2026-10-25-claude-code.md)):
60/60 rule checks passed across scoring, tailoring and onboarding. Every buried
hard requirement was caught and capped, a "preferred" MBA was not mistaken for a
required one, and no resume claimed a skill the user lacked. An AI judge found 4
small stretches in self-written sentences ("leads incident response" for someone
who wrote the runbook). The playbooks gained a check for exactly those, and two
repeat runs found none.

Run it with your own agent: `python3 evals/run.py`.

## Contributing

Bug reports, new job-board adapters, starter lists for other regions and
industries, and playbook improvements are all welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md). If Job Sherpa helps you, a ⭐ helps others
find it.

## License

[MIT](LICENSE). The bundled Source Sans 3 font is under the
[SIL Open Font License](templates/fonts/OFL.txt).
