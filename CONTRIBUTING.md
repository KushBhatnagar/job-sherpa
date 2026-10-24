# Contributing to Job Sherpa

Thanks for helping. Job Sherpa is used by people in the middle of a job search,
so changes should make it more honest, more reliable or easier to start with.

## Good first contributions
- **Companies:** add verified companies to a starter list, or a new list for
  your region or industry (`starter-lists/<name>.yaml`). Run
  `bin/sherpa check-companies` against it first.
- **Job boards:** a new public ATS adapter in `sherpa/sources/` (same output
  shape as `greenhouse.py`), plus a test. Only official public APIs: no
  scraping, and nothing that breaks a site's terms.
- **Playbooks:** sharper steps, better questions in
  `onboarding/questionnaire.md`, lessons from your own search.
- **City aliases** in `sherpa/enrich.py` (`_ALIASES`).

## Ground rules
1. **Standard library only** in `sherpa/`, apart from Typst for rendering.
   It keeps setup to one `pip install`.
2. **Keep the hard rules** in `AGENTS.md` intact. A change that makes it
   easier to invent a claim, skip a check or scrape a site won't be merged.
3. **No personal data** in issues, pull requests, tests or examples. Use the
   fictional sample user in `examples/alex/` (or extend it). Check your diff
   for anything from `me/` before you push.
4. Add or update a test in `tests/`, and run:
   ```bash
   python3 -m unittest discover -s tests
   ```

## Pull requests
Fork, branch, commit, open a PR describing what changed and why. Small,
focused PRs are reviewed fastest. Discuss big changes in an issue first.

## Reporting bugs
Open an issue with the command you ran, what you expected, and what happened.
Replace any personal details in the output before pasting it.
