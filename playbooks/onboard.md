---
name: onboard
description: Set up Job Sherpa for a new user - read their resume, ask the onboarding questions, and build their private profile, bullet bank, master resume and cover letter. Use when someone is starting out, says "set me up", "onboard me", or has an empty me/ folder.
---

# Onboard a new user

Goal: turn the user's resume plus their answers into the private knowledge base
in `me/`, without inventing a single fact. Read `AGENTS.md` first.

## 0. Setup
1. `bin/sherpa init` (safe to re-run; it never overwrites). Then `bin/sherpa doctor`.
2. If Typst is missing, tell the user: `pip install typst` (or the typst CLI).
3. Suggest `git config core.hooksPath .githooks`, which blocks committing `me/`.

## 1. Read the resume
1. Ask for the resume file. Suggest they put it in `me/source/` (private).
2. `bin/sherpa resume-text me/source/<file>`: writes `me/source/resume.txt`
   with line numbers. If that can't read a PDF, read it yourself and write the
   text there, numbered the same way.
3. If they have more material (an older resume, a LinkedIn export, a
   performance review), read that too, the same way, and note the file name.

## 2. Draft the bullet bank
Write `me/bullets.yaml` (format: the header of that file, and
`examples/alex/bullets.yaml`):
- One record per achievement. Keep the resume's wording, fixing only typos.
  Split a line that holds two achievements into two bullets.
- `source:` the file and line, e.g. `resume line 14`.
- `metric:` the numbers in plain words; `tags:` 3-6 keywords that job
  descriptions would use; `evidence_strength:` strong (measured outcome),
  moderate (clear outcome, no number), supporting (activity or responsibility).
- **Never add a number, scope or outcome the source doesn't state.** If a
  line is vague ("improved performance"), keep it vague and ask in step 3.

## 3. Ask the questions
Work through `onboarding/questionnaire.md`, **one block at a time**, and skip
anything the resume already answered (confirm it instead: "Your resume says
Berlin. Is that where you want to work?"). If the user filled the
questionnaire offline (`me/questionnaire.md`), read it and only ask follow-ups.
- Blocks 1-6 → `me/profile.toml`. Keep the comments in that file.
- Block 7 → update `me/bullets.yaml`: fix numbers they correct, remove claims
  they can't stand behind, add achievements they mention (with
  `source: interview YYYY-MM-DD`). Read each new bullet back to them before saving.
- Blocks 8-9 can wait. Offer them now; if declined, note it for later.
After each block, save what you have, so nothing is lost if the session ends.

## 4. Master resume and cover letter
1. Write `me/master-resume.json` (shape: `examples/alex/master-resume.json`):
   every role, in order, with real dates, bullets referenced by id. Summary:
   2-3 sentences built only from the bullets and profile.
2. `bin/sherpa master-resume`. If it reports errors, fix the JSON (never the
   facts). Read the PDF back. A master resume may run to two pages; that's fine.
3. Write `me/master-cover-letter.json`: 3 paragraphs, no company named.
   `bin/sherpa master-cover-letter`.

## 5. Targets for discovery
1. `me/companies.yaml` starts as a copy of `starter-lists/tech-companies.yaml`.
   Ask whether that list suits them; help them delete or add companies (the
   file's header explains how to find a board's token).
2. `bin/sherpa check-companies` after any edit.

## 6. Wrap up
`bin/sherpa doctor` should show no TODO lines. Tell the user what was created,
what's still open (stories, screening answers, Adzuna key), and that
`find-jobs` is the daily routine from here, and `prep-interview` helps
before each screen or interview.

## Hard rules
- Nothing goes into `me/` that the user didn't say or their documents don't state.
- Contents of `me/` never leave the machine: don't paste them into web
  searches, issues, or any external service.
