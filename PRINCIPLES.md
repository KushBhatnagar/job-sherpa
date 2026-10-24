# Why Job Sherpa works the way it does

Each rule below exists because the obvious way to automate a job search goes
wrong in a specific way. The thresholds are defaults you can change in
`me/profile.toml`; the reasoning is the part worth keeping.

## 1. Every claim traces to a real bullet

An AI that writes your resume will happily improve it: a 35% becomes a 40%, a
contribution becomes leadership, a skill you touched becomes one you own. It
reads well until an interviewer asks about it.

So your achievements live in one file, `me/bullets.yaml`, each recording where
it came from (a resume line, an interview answer). Tailoring may align
vocabulary to the job description; it may not change a number, scope or
outcome. `sherpa tailor-resume` checks this mechanically: a bullet with no id,
or any number that isn't in the original, stops the render.

## 2. A missing hard requirement caps the score

It's tempting to score a job highly because the work matches what you've done.
But the fast "no" in hiring rarely comes from keywords. The often-quoted claim
that 75% of resumes are auto-rejected traces back to a 2012 sales pitch; in a
2025–26 survey of recruiters using Workday, iCIMS and Greenhouse, 92% said their
applicant tracking system does not auto-reject on resume content or formatting.
Greenhouse's own documentation says the only automatic rejection it supports is
knockout questions, such as years of experience or work authorization.

Recruiters screen on stated minimums before they read anything else, and a
great match on the work does not get past someone counting years. So any unmet
minimum (years, degree, certification, work authorization) caps the fit score
at 6 by default. Stretch roles can still be applied to; they just never
outrank roles you actually qualify for.

## 3. Name gaps honestly, never restate a shortfall

Saying "I haven't worked in healthcare, but here's what transfers" reads better
than silence, especially for a senior candidate. But a sentence like "5 years
against the 8 this role asks for" hands the screener the rejection reason in
your own words.

The rule: name **domain** gaps in one sentence, then what transfers. Never
restate a **numeric** bar you fall short of. That isn't hiding anything: the
dates and the degree are on the resume.

## 4. Never score a job blind

Aggregator APIs return 500-character excerpts, and an excerpt usually shows the
company's pitch, not the requirements. The years gate, the required degree or
the required domain tend to sit further down. So a job without its full
description can't be scored at all: Sherpa first looks for the same posting on
the company's own public job board, and if it can't match it confidently, it
asks you to paste the description.

The matching is deliberately strict. A company can have three "Senior
Engineer" roles open in different cities; attaching the wrong description is
worse than having none.

## 5. Location is a flag, not a filter

Postings name locations loosely: a city, a region, "hybrid", "remote within
the EU". Dropping a job because its location doesn't match exactly can hide a
role you'd take. So when the work fits but the location looks off, the job is
scored on its content and the mismatch goes in the score's risks; you decide.
Only legal blockers (work authorization) are hard gates.

## 6. A filter that fails silently hides jobs silently

Text filters on title and location will be wrong sometimes. "Remote, U.S."
looks like "remote" to a naive filter, and a missing spelling of a city drops
jobs just as quietly. So every `sherpa discover` run ends with a report of
what the filters dropped, with a "worth a look" list of locations that might be
reachable after all. The same goes for job boards: a company listed on the
wrong board simply never shows up, which is why `sherpa check-companies`
exists. And if every source fails, discovery says so instead of reporting
"0 new jobs".

## 7. Old postings aren't worth the effort

Tailoring an application for a posting that has been open for two months is
rarely worth it. Jobs older than 60 days are dismissed automatically and left
off shortlists.

## 8. One resume look, one page

A tailored resume that spills onto a second page, with one bullet stranded
there, looks careless. Sherpa reports the page count after every render, and
the fix is always to cut the least relevant bullets, never to shrink the font:
every resume you send should look the same.

Typographic ligatures are turned off in the templates because they break text
extraction ("Microsoft" can come out as "Microsof"), and applicant tracking
systems read the extracted text, not the pretty PDF.

## 9. You submit, Sherpa prepares

Job Sherpa never applies, sends or posts anything for you. Applications are
judgment calls with your name on them.

## 10. Your data stays yours

Everything personal lives in one gitignored folder, `me/`. A git hook refuses
to commit it, and the agent instructions forbid pasting it anywhere external.
Job Sherpa never scrapes sites whose terms forbid it: it reads public job-board
APIs that companies publish so their jobs get found, and you paste the rest.
