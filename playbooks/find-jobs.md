---
name: find-jobs
description: The daily job-search routine - discover new postings, fill in missing job descriptions, score them, and present the best matches. Use when asked to find jobs, check for new postings, or run the daily search.
---

# Find jobs (daily routine)

1. `bin/sherpa discover` (or `--source X` for one source). Report per source
   what came back, then the end of the output:
   - **Failed sources** (`! N of M source(s) failed`): name them; those
     boards weren't checked. If it says every source failed, stop and say so:
     "0 new" then means nothing was checked, not a quiet day.
   - **What the filters dropped**: pass on any `worth a look` locations and
     near-miss titles in a line or two. If one should have been kept, suggest
     the profile change (`[targets]` in `me/profile.toml`) and let the user
     decide. Never edit the profile on your own from this report.
2. Jobs the user found elsewhere (LinkedIn, referrals, careers pages):
   `bin/sherpa add-job --company X --title Y --location Z --url U --file jd.txt`
   with the JD they pasted. Never fetch LinkedIn, Naukri, Indeed or any site
   whose terms forbid automated access; the user pastes from those.
3. `bin/sherpa enrich-jd`: finds full JDs for excerpt-only jobs (Adzuna) on
   the company's own board. Report the unresolved ones; they stay unscored
   until the user pastes a JD (`bin/sherpa set-jd <id>`).
4. Run the `score-fit` playbook on every unscored job and every job flagged
   `rescore_needed`. It ends with `bin/sherpa shortlist-export`.
5. Present: 8-10 (act now), 5-7 (worth a look), below 5 (dismissed). For the
   ones worth acting on, suggest next steps: `bin/sherpa shortlist <id>`, a
   tailored resume (`tailor-resume`), and checking for a referral.
6. Weekly: `bin/sherpa followups` for applications that have gone quiet.

Nothing is ever submitted for the user. Sherpa prepares; the user applies.
