---
name: score-fit
description: Score how well a job fits the user, from its full job description and their profile and bullets. Use when asked to score, triage or evaluate jobs in the inbox, or right after a job is added.
---

# Score fit

Deciding whether a job is worth the user's time is judgment work, so it lives
here, not in code. `sherpa score` only stores the result (and enforces two
rules: no score without a full JD, and the hard-gate cap).

## Read first
- `me/profile.toml`: targets, hard facts, dealbreakers, `[search].hard_gate_cap`.
  If it's mostly empty, stop and suggest the onboard playbook. Don't guess
  someone's preferences.
- `me/bullets.yaml`: what the user has actually done.

## For each job
1. `bin/sherpa inbox` lists new jobs, unscored first. Also rescore any job whose
   fit detail says `rescore_needed`.
2. `bin/sherpa show <id> --full` and read the WHOLE description.
   - `needs_full_jd` in the fit detail means you only have an excerpt. Run
     `bin/sherpa enrich-jd --job-id <id>`. If it can't find the posting, ask
     the user to paste the JD (`bin/sherpa set-jd <id>`) or leave the job
     unscored. **Never score from an excerpt**: excerpts hide requirements
     (a years gate, a required degree, a domain) that change the score.
3. **Hard gates first.** List every stated minimum the user does not meet:
   years of experience above `[experience]` figures, a required degree,
   certification, citizenship, clearance, a language. Each goes in
   `hard_blockers`, and **any hard blocker caps the score at
   `hard_gate_cap` (default 6)**, however strong the rest is. Recruiters
   screen on these before anything else; a great domain match doesn't get
   past someone counting years. Stretch roles can still be applied to; they
   just never outrank roles the user qualifies for.
   Preferred/"nice to have" items are not hard gates.
4. **Location is a flag, not a filter.** If the work fits but the location is
   off (another city, remote restricted to another country), score it on
   content and put the mismatch in `risks`. The user decides. A legal blocker
   (work authorization they don't have) is a hard blocker.
5. Score 1-10 on the dimensions that matter for this job (domain match,
   seniority fit, core-skill overlap, logistics). Don't force dimensions that
   don't apply. Check the dealbreakers.
6. Write an `angle`: one sentence on how to position the user for this job,
   using only what's in their bullets. List `keyword_gaps`: what the JD asks
   for that no bullet supports. Real gaps, not padding.
7. Store it (the JSON is one shell-quoted string):
   `bin/sherpa score <id> --score N --json '{"dimensions": {...}, "angle": "...", "keyword_gaps": [...], "hard_blockers": [...], "risks": [...]}'`
8. Below 5 with a clear reason: `bin/sherpa dismiss <id> --reason "..."`.

## Finish every pass with
`bin/sherpa shortlist-export`: writes a dated shortlist of jobs at or above
`[search].shortlist_min_score`, which is the list the user applies from.
Then report: 8-10 (act now), 5-7 (worth a look), below 5 (dismissed, with reasons),
and the shortlist file's path.

## Hard rule
Never credit the user with experience they don't have to lift a score. A low
score with an honest reason is worth more than a flattering one.
