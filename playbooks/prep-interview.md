---
name: prep-interview
description: Prepare the user for a recruiter screen or interview for one job - likely questions, their own stories matched to the job, screening answers, and questions to ask. Use when the user has a screen or interview coming up, or asks to prepare for one.
---

# Prepare for an interview

Goal: a one-page prep sheet for one job, built from the user's own stories and
answers. Interviews ask for what surrounds a result (why it started, what
nearly went wrong, what they decided), so this works from `me/stories.md`, not
just the bullets.

## Steps
1. Ask which job. `bin/sherpa applications` lists open applications with
   their application id, job id and last event. Ask what
   kind of conversation: recruiter screen, hiring manager, panel, case or
   assignment. Ask who they're meeting, if they know.
2. `bin/sherpa show <job id> --full`: the JD, plus `angle`, `keyword_gaps` and
   `hard_blockers` from score-fit.
3. Read `me/stories.md`, `me/screening-answers.md`, `me/profile.toml` and the
   resume sent for this job (in `me/applications/` or `me/drafts/`).
   If stories or screening answers are still empty, run blocks 8-9 of
   `onboarding/questionnaire.md` with the user first. Their words, not yours.
4. Write `me/drafts/<id>__.../interview-prep.md` (the job's draft folder):
   - **The role in 3 lines:** what they need, in the JD's own terms.
   - **Your pitch:** their "tell me about yourself", adjusted to this job's
     angle. Keep their wording; only change what to lead with.
   - **Likely questions → your story:** 6-10 questions this JD invites, each
     mapped to one of their stories (by name) or a bullet id. Where no story
     fits, say so plainly and help them think of a real example. Never write
     one for them.
   - **The hard ones:** each `hard_blocker` and `keyword_gap`, and an honest
     way to answer it: what transfers, without restating a numeric shortfall.
   - **Logistics answers:** notice period, location, salary approach from
     `[compensation]` (ask for their band first; never write the walk-away
     number into the sheet unless the user asks).
   - **Questions to ask them:** 3-5, specific to this JD.
5. Offer a mock round: ask the likely questions one at a time, let them
   answer, then give short, specific feedback (too long, no result stated,
   "we" where it should be "I").
6. After the interview: `bin/sherpa log <application id> --event <type> --notes "..."`
   (recruiter_screen, hm_round, panel, assignment, offer, rejected). Add any
   new story they told to `me/stories.md`, and any new result to
   `me/bullets.yaml` with `source: interview YYYY-MM-DD`.

## Hard rules
- Every story and number comes from the user's files or what they tell you.
  If a story is thin, ask questions; don't fill the gaps.
- The prep sheet is private (`me/`); never paste it anywhere external.
