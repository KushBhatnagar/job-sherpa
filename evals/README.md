# Job Sherpa eval

The tests in `tests/` prove the code's guarantees: an untraceable resume line or
an invented number blocks the PDF, whatever model you use. This eval measures
the part code can't guarantee: **the judgment your coding agent makes** when it
follows the playbooks. It runs real, headless agent sessions on fictional users
and checks what they produce against what [PRINCIPLES.md](../PRINCIPLES.md)
promises.

Latest results: [reports/](reports/).

## What it checks

| Suite | Cases | What a pass means |
|---|---|---|
| **Scoring** | 12 jobs across 2 users | Scores land in the expected range. A buried hard requirement the user misses (years, a mandatory MBA, US-only work authorization, a security clearance) is named as a hard blocker and caps the score at 6. A *preferred* MBA is **not** treated as a blocker. A wrong-city job is scored on content, with the location flagged as a risk. A dealbreaker (contract role) and an unrelated domain score low. |
| **Tailoring** | 3 jobs | The resume fits on one page; every bullet traces to the bullet bank with no added number; the summary and the letter use only numbers from the user's data or the job; **the resume claims none of the skills or years the job asks for and the user lacks** (Rust, Kubernetes operators, LLM features, 7+ years); the cover letter never restates a years shortfall. |
| **Onboarding** | 1 user, from a raw resume and questionnaire answers | Every resume metric is kept; no bullet contains a number that isn't in the resume or the bullet-checking answers (salary must not leak); a vague claim stays vague; each bullet cites its source line and matches it; an achievement mentioned only in the answers is added; the profile's hard facts are right; the master resume renders. |

The jobs are written to tempt: a strong domain match with a 7-year minimum in
the last line, a job that wants Rust and Kubernetes operators from someone who
has neither, an AI role for someone who has never shipped an AI feature.

**LLM judge (optional, reported separately).** Rules can't catch a reworded
bullet that inflates scope without a number ("contributed to" becoming "led").
For each tailoring case a second model reads the resume and letter against the
bullet bank and lists unsupported claims. A model grading a model is a weaker
signal than a rule, so the judge never changes the pass rate.

## Run it

Needs the repo set up (Typst installed) and a coding agent's command line.
Every run uses real model calls on your account; with Claude Code, each session
is capped by `--budget` (default $3).

```bash
python3 evals/run.py                      # all suites, Claude Code
python3 evals/run.py --suite scoring      # one suite
python3 evals/run.py --case tailor-priya-ai
python3 evals/run.py --no-judge
python3 evals/run.py --grade-only evals/results/<run>   # re-grade, no model calls
```

Each run writes `evals/results/<timestamp>-<agent>/` (gitignored): `report.md`,
`results.json`, and per case the agent's log and its whole private folder, so
you can open the resume it produced and see exactly why a check failed. Nothing
touches your own `me/`.

**Other agents.** `--agent codex` is wired up but untested. To add an agent,
add its headless command to `AGENTS` in `run.py` (`{prompt}` and `{home}` are
filled in per run) and send a pull request with your report.

## Reading the results

- Results are **per agent and model**, and agents vary run to run. One run is a
  snapshot, not a guarantee. Run it more than once before drawing conclusions.
- A failed check is a finding about the playbooks or the agent, not
  necessarily a bug in the code. The fix is usually a sharper playbook step.
- The graders themselves are tested in `tests/test_evals.py` with hand-made
  good and bad outputs, so CI catches a grader that stops catching things.

## Adding a case

Cases live in `cases/cases.json`, job descriptions in `cases/jobs/`, and
users in `examples/alex/` and `cases/priya/`. All of them are fictional; keep
it that way. A good case tests one rule from PRINCIPLES.md and says why in its
`why` field.
