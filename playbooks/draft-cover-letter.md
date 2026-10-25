---
name: draft-cover-letter
description: Write a cover letter for one job that addresses real gaps honestly instead of hiding them. Use when asked for a cover letter, or to finish an application after tailor-resume.
---

# Draft a cover letter

## Steps
1. `bin/sherpa show <id> --full`: the JD, plus `angle`, `keyword_gaps` and
   `hard_blockers` from score-fit.
2. Write 3-4 paragraphs (~350-450 words):
   - Why this role and company: specific, from the JD, not flattery.
   - 1-2 paragraphs of evidence from `me/bullets.yaml`, each tied explicitly
     to something the JD asks for.
   - If there's a **domain** gap (a technology, industry or product type the
     user hasn't worked in), name it in one sentence, then say what transfers.
     That reads better than silence and better than vague hedging.
3. **Never restate a numeric bar the user falls short of**: years of
   experience, a degree level, a certification. "5 years against the 8 you
   ask for" hands the screener the rejection reason. Not restating it isn't
   dishonest; the dates and degree are on the resume. If experience comes up,
   use `[experience].role_years_note` as a strength, never as a shortfall.
4. Never invent a qualification or a number. Numbers must come from
   `bullets.yaml`, `profile.toml`, or the JD itself; the render step checks.
   The words are not checked by code: before rendering, run the
   **Free-text check** in `playbooks/tailor-resume.md` on every sentence
   (no upgraded verbs, no skill moved to another role, no added reach, no
   invented order of events, no ability claimed from adjacent experience).
5. Payload in `me/drafts/<id>-letter.json`:
   `{"paragraphs": ["...", "..."], "angle": "..."}` (optional: `"date"`,
   `"greeting"`, `"sign_off"`, `"closing"`). Then:
   `bin/sherpa tailor-cover-letter <id> --data me/drafts/<id>-letter.json`
6. It must fit on one page. If it spills, tighten the paragraphs.
7. Read the PDF back and report its path. Nothing is submitted for the user.
