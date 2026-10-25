# Eval report: Claude Code, 25 Oct 2026

**Setup:** Claude Code 2.1.310 with its default model, headless (`claude -p`),
one session per case, capped at $3. Fictional users: Alex (backend engineer,
Berlin) and Priya (product manager, Bengaluru). Cases and expectations:
[`cases/cases.json`](../cases/cases.json). Total model cost for everything
below: about $3.50.

## Headline

| | Rule checks | LLM judge: unsupported claims |
|---|---|---|
| Run 1: all suites, original playbooks | **60/60** | 4 (in 3 tailoring cases) |
| Run 2: tailoring, after the playbook fix | **24/24** | **0** |
| Run 3: tailoring, repeat | **24/24** ¹ | **0** |

¹ The first attempt at one case failed because the eval harness blocked the
agent's commands (see "Harness issue" below). After the harness fix the case
was re-run and passed 8/8. It isn't counted as a Job Sherpa failure.

## Run 1: all suites (60/60 rule checks)

**Scoring (22/22).** Every score landed in its expected range across 12 jobs.
Each buried hard requirement was named as a blocker and capped the score: a
7-year minimum (scored 6), a mandatory MBA (6), US-only work authorization (4),
a 12-year minimum (6), US citizenship plus security clearance (3). The
"MBA preferred" job was correctly **not** treated as a blocker (8). The
right-work-wrong-city job scored 8, with the location flagged as a risk. The
contract role (a dealbreaker) scored 4, and the semiconductor and frontend jobs
scored 1-2.

**Tailoring (24/24).** All three resumes and letters fit on one page; every
bullet traced to the bullet bank with no added number; the letters named gaps
honestly ("I have not written Kubernetes operators or controllers, and I have
not used Rust in production") without restating a years shortfall; none of the
planted skills (Rust, operators, LLM features, 7+ years) appeared on a resume.

**Onboarding (14/14).** From a raw resume and questionnaire answers, the agent
kept all 9 metrics, invented no number (the vague "improved batch jobs" stayed
vague), cited a matching source line for every resume bullet, added the
achievement mentioned only in the answers, filled the profile's hard facts
correctly, and the master resume rendered.

**LLM judge: 4 unsupported claims**, all in sentences the agent wrote itself
(summary or cover letter), none involving a number:

| Case | Claim | Why it's unsupported |
|---|---|---|
| Alex, Kubernetes job | Summary: "Leads incident response" | He wrote the runbook and mentored on-call engineers |
| Alex, Kubernetes job | Letter: "an extension point that many teams build on" | No bullet says other teams built on it |
| Priya, AI job | Letter: her engineering background "lets me work comfortably with ML engineers" | She built Java APIs, no ML work |
| Priya, growth job | Letter: "Before that, I owned the UPI AutoPay flow" | The bullets give no order of events |

## The fix

These are the slips the code can't catch: the claim checker reads numbers and
bullet ids, not meaning. So the tailoring and cover-letter playbooks gained a
**free-text check**: before rendering, point every claim in a self-written
sentence at its bullet, and avoid five named slips (upgraded verbs, a skill
moved to another role, added reach, an invented order of events, an ability
claimed from adjacent experience).

## Runs 2 and 3: tailoring after the fix

Both runs: all rule checks pass, and the judge found **no unsupported claims**
in any of the three cases.

## Harness issue found along the way

In run 3, one session couldn't run `bin/sherpa` at all: the eval only allows a
short list of command forms, and the agent tried forms outside it (`cd … &&`,
an environment-variable prefix). It reported the block and refused to
hand-build a resume without the claim check, which is the right behaviour. The
harness now tells the agent it's already in the repo with `SHERPA_HOME` set,
and allows `cd`.

## Limits

- **Small sample:** 1 run of scoring and onboarding, 3 runs of tailoring, on 2
  fictional users. Agents vary run to run; treat this as evidence, not proof.
- **One agent:** Claude Code only. Results with other agents and models may
  differ; reports welcome.
- **The judge is a model too.** It found real slips, but its verdicts vary
  between runs (one finding appeared in only one of two gradings of the same
  output). It never affects the rule-check pass rate.
- **The skills section is not traced by code.** Skills come from the user's
  master resume. The eval's planted-skill check covers it, and the judge reads
  it, but `sherpa tailor-resume` itself doesn't check it.
