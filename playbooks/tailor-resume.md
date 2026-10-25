---
name: tailor-resume
description: Build a resume tailored to one job from the user's bullet bank, using the job description and its fit angle. Use when asked to tailor a resume, write a resume for a job, or prepare an application.
---

# Tailor a resume

Choosing which bullets to lead with, and aligning their vocabulary to the job,
is judgment work. `sherpa tailor-resume` checks every claim against
`me/bullets.yaml` and renders; it refuses anything it can't trace.

## Start from the master
`me/master-resume.json` holds every role with its canonical title, order and
dates. Start from its structure and trim; don't rebuild the role list.

## Steps
1. `bin/sherpa show <id> --full`: the JD, and the `angle` and `keyword_gaps`
   from score-fit if it ran.
2. `bin/sherpa bullets --tags a,b,c` with tags taken from the JD's own words.
   That's a starting list: read each bullet's full text and its `notes`
   (some say "never use with b-00X").
3. Pick the bullets that matter for this job, usually 8-14 in total:
   - Lead each role with what this JD values most.
   - If the JD gates on years in a role, lead the relevant roles with the
     bullets that most clearly show that role's work. A recruiter counting
     years reads the bullets.
   - **Keep every role** so the timeline has no gaps; trim minor roles to 1-2
     bullets instead of dropping them.
   - Two bullets that describe the same result must not both appear.
4. **Rewrite guardrail.** You may align vocabulary (JD says "experimentation",
   bullet says "A/B testing": use their word). You may shorten. You may NOT
   change a number, add scope, inflate a title, or claim an outcome the
   bullet doesn't state. A JD keyword with no supporting bullet belongs in the
   cover letter's honest-gap sentence, not in the resume.
5. Summary: 2-3 sentences that mirror the JD's framing using only facts from
   the bullets and profile. State experience exactly as
   `[experience].role_years_note` says, the same in every document.
   The code only checks the summary's numbers, so check the words yourself
   (see "Free-text check" below).
6. Write the payload to `me/drafts/<id>-resume.json`. Same shape as
   `me/master-resume.json`; each bullet is either an id (`"b-001"`, used
   verbatim) or `{"id": "b-001", "text": "aligned wording"}`. Add
   `"angle": "..."`. Then:
   `bin/sherpa tailor-resume <id> --data me/drafts/<id>-resume.json`
7. If it reports errors, fix the wording to match the bullet. `--force` is
   only for a false alarm you can explain to the user (e.g. "2nd" read as a
   number). Never use it to get a claim through.
8. **One page** (when `one_page_resume` is on): if it reports more, cut the
   least relevant bullets and render again. Never shrink fonts or margins:
   every resume keeps the same look.
9. Read the PDF back, then report its path. Nothing is submitted:
   the user reviews, applies, then logs it with `bin/sherpa apply --job-id <id>`.

## Free-text check (summary, and the cover letter too)
Before rendering, read every sentence you wrote yourself and point each claim
at the bullet that supports it. Eval runs found these slips; avoid them:
- **Upgrading the verb.** "Wrote the incident-response runbook" is not
  "leads incident response"; "mentored" is not "managed".
- **Moving a skill to another role.** If Go appears only in the logistics
  role, don't write "Go for logistics and payments".
- **Adding reach or impact.** "Built a platform" is not "a platform many
  teams build on" unless a bullet says so.
- **Inventing an order of events.** Two bullets from the same role have no
  "before" and "after" unless their dates say so.
- **Claiming an ability from adjacent experience.** Java APIs do not mean
  "comfortable working with ML engineers".
If a sentence fails, cut it or reword it down to what the bullet says.

## Hard rule
Every claim must trace to a bullet in `me/bullets.yaml`. If the user tells you
about a new achievement while tailoring, add it to `bullets.yaml` first (with
`source: interview YYYY-MM-DD`), read it back to them, then use it.
