# The onboarding questionnaire

Job Sherpa learns about you from two inputs: **your resume** and **your answers
to the questions below**. From them it builds your private knowledge base in
`me/`: `profile.toml`, `bullets.yaml`, `stories.md` and `screening-answers.md`.

Two ways to answer:

1. **With your coding agent (recommended).** Ask it to run the onboard playbook
   (`playbooks/onboard.md`). It reads your resume first, so it only asks what
   the resume doesn't already say, one block at a time.
2. **On your own.** Copy this file to `me/questionnaire.md`, answer under each
   question, then ask your agent to run the onboard playbook on it.

Rules that apply to every answer:

- **Only true things.** Everything here can end up in an application. If you're
  unsure of a number, say so; the agent will leave it out rather than guess.
- **Your words beat polished words.** The agent tidies; it doesn't invent.
- **Skip anything you don't want to answer.** Missing answers make the agent
  ask later or stay conservative; they never get filled in for you.

Each question shows where the answer goes, like `→ profile.toml [targets].titles`.

---

## Block 1: Contact and basics

1. Your name as it should appear on a resume. → `[contact].name`
2. City and country for the resume header. → `[contact].location`
3. Phone and email for applications. → `[contact].phone`, `.email`
4. Links worth showing (LinkedIn, GitHub, portfolio). → `[contact].links`
5. Paper size: A4 or US Letter? → `[documents].paper`

## Block 2: What you're looking for

1. Which job titles do you want? List the exact words postings use.
   → `[targets].titles`
2. Which nearby titles should the system mention but not store (a step up, a
   step sideways)? → `[targets].near_miss_titles`
3. Which titles contain your keywords but are NOT for you (e.g. "sales
   engineer" for a software engineer)? → `[targets].exclude_title_words`
4. What seniority are you targeting? → `[targets].seniority`
5. In one or two sentences: what must the job really be, whatever its title?
   → `[targets].role_types`
6. Industries you want, and industries you won't work in.
   → `[targets].industries_want`, `.industries_avoid`

## Block 3: Where you can work

1. Which cities or countries can you work in on-site or hybrid?
   → `[targets].locations`
2. Remote: anywhere in the world, only certain regions, or not at all?
   → `[targets].remote`, `.remote_regions`
3. Are you open to relocating? → `[targets].relocation`
4. Where can you legally work without visa sponsorship?
   → `[experience].work_authorization`
5. Time zones you can overlap with, and how much travel is OK. → `[logistics]`

## Block 4: Hard facts (scoring compares these to job requirements)

1. Total years of professional experience. → `[experience].total_years`
2. Years in the kind of role you're targeting, and the month you count them
   from. Pick one figure and use it everywhere: a resume and a cover letter
   that disagree look careless. → `[experience].role_years`, `.role_years_since`,
   `.role_years_note`
3. Highest degree, and any certifications. → `[experience]`
4. Notice period. → `[logistics].notice_period`

## Block 5: Money (private, never written into a document)

1. Currency, current pay, and your walk-away number (below this is a no).
2. What counts toward that number (base only? bonus? equity?).
   → `[compensation]`

## Block 6: Dealbreakers

1. What would make you turn down an otherwise good offer? (Contract-only,
   on-call load, a bond, a title that hides a different job...)
   → `[targets].dealbreakers`

## Block 7: Checking your bullets (the agent drafts these from your resume)

For each achievement on your resume, the agent asks:

1. **Is the number right, and where does it come from?** (A dashboard, a
   review, your own estimate?) If you can't stand behind it in an interview,
   it gets softened or removed.
2. **What did you personally do**, versus your team?
3. **Anything missing?** Results that never made it onto the resume: things
   you're proud of, problems you solved, what people thanked you for.
   → `bullets.yaml` (each bullet records its `source`)

## Block 8: Stories (for interviews; can be done later)

Pick your 3-5 strongest bullets. For each:

1. Why did the work start? What was the situation?
2. What nearly went wrong, and what did you do about it?
3. What decision did you make that someone else might not have?
4. What would you do differently now?

Also one story each for: a failure, a disagreement with a manager or peer, and
a time you changed your mind. → `stories.md`

## Block 9: Recruiter-screen answers (can be done later)

1. Tell me about yourself (60-120 words, spoken).
2. Why are you looking?
3. Salary expectations: what you'll say, and when you'll share your number.
4. The question you dread most, and an honest answer to it.
   → `screening-answers.md`

## Block 10: Your job search so far (optional, improves scoring)

1. Roles you applied to recently, and what happened (rejections included).
2. Any pattern you've noticed in what gets responses?
   → logged with `sherpa apply` and `sherpa log`; patterns go in your notes
