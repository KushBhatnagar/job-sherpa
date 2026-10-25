"""The eval graders, checked against hand-made agent outputs (no agent needed)."""
import json
import shutil
import sys
import unittest

import helpers
from sherpa import render

sys.path.insert(0, str(helpers.REPO / "evals"))
import graders  # noqa: E402

CASES = json.loads((helpers.REPO / "evals" / "cases" / "cases.json").read_text())
JD = (helpers.REPO / "evals" / "cases" / "jobs" / "a-years-gate.md").read_text()   # asks for 12 years


class ShortfallRegexTest(unittest.TestCase):
    def test_catches_restated_shortfall(self):
        for s in ("I bring 5 years against the 8 years this role asks for.",
                  "With 4+ years versus the 7+ years required, I",
                  "While you ask for 7 years, I have 4."):
            self.assertIsNotNone(graders.SHORTFALL_RE.search(s), s)

    def test_allows_honest_strengths(self):
        for s in ("I bring 4+ years of product management in payments.",
                  "Over 8 years I have built event-driven services.",
                  "I haven't shipped LLM features yet, but here is what transfers."):
            self.assertIsNone(graders.SHORTFALL_RE.search(s), s)


class ScoringGraderTest(helpers.AlexHome):
    def test_scores_checked_against_expectations(self):
        case = next(c for c in CASES["scoring"] if c["id"] == "score-alex")
        ids = {}
        for job in case["jobs"]:
            out = self.run_cli("add-job", "--company", job["company"], "--title", job["title"],
                               "--file", str(helpers.REPO / "evals" / "cases" / "jobs" / job["file"]))
            ids[job["file"]] = int(out.split("#")[1].split(":")[0])
        # A good agent: right scores. Then one mistake: the years gate scored 8 with no blocker.
        self.run_cli("score", str(ids["a-strong-fit.md"]), "--score", "8", "--json", '{"angle": "x"}')
        self.run_cli("score", str(ids["a-years-gate.md"]), "--score", "8", "--json", '{"angle": "x"}')
        self.run_cli("score", str(ids["a-frontend.md"]), "--score", "3", "--json", '{}')
        self.run_cli("score", str(ids["a-clearance.md"]), "--score", "5", "--json",
                     '{"hard_blockers": ["US clearance"]}')
        checks = {c.name: c for c in graders.grade_scoring(case, self.home, ids)}
        self.assertTrue(checks["a-strong-fit: score in range"].passed)
        self.assertTrue(checks["a-strong-fit: no false hard blocker"].passed)
        self.assertFalse(checks["a-years-gate: score in range"].passed)
        self.assertFalse(checks["a-years-gate: hard blocker named"].passed)
        self.assertTrue(checks["a-frontend: score in range"].passed)
        self.assertTrue(checks["a-clearance: hard blocker named"].passed)


@unittest.skipUnless(render.typst_backend(), "Typst not installed")
class TailoringGraderTest(helpers.AlexHome):
    def _render(self, bullets, skills, letter):
        out = self.run_cli("add-job", "--company", "Logibase", "--title", "Principal Backend Engineer",
                           "--file", "-", stdin=JD)
        job_id = int(out.split("#")[1].split(":")[0])
        payload = json.loads((self.home / "master-resume.json").read_text())
        payload["experience"] = [payload["experience"][0]]
        payload["experience"][0]["roles"][0]["bullets"] = bullets
        payload["skills"] = skills
        (self.home / "r.json").write_text(json.dumps(payload))
        (self.home / "l.json").write_text(json.dumps({"paragraphs": [letter]}))
        self.run_cli("tailor-resume", str(job_id), "--data", str(self.home / "r.json"))
        self.run_cli("tailor-cover-letter", str(job_id), "--data", str(self.home / "l.json"))
        return job_id

    def test_honest_documents_pass(self):
        job_id = self._render(["b-001", "b-003"], [{"label": "Languages", "value": "Go, Python"}],
                              "I bring 8 years of backend engineering and event-driven services in Go.")
        case = {"id": "t", "forbidden_in_resume": ["Rust", "operator"]}
        checks = graders.grade_tailoring(case, self.home, job_id, JD)
        self.assertTrue(all(c.passed for c in checks), [c for c in checks if not c.passed])

    def test_planted_skill_and_shortfall_are_caught(self):
        # The claim checker doesn't read the skills section: the eval must catch it.
        job_id = self._render(["b-001"], [{"label": "Languages", "value": "Go, Rust"}],
                              "I bring 8 years against the 12 years you ask for.")
        case = {"id": "t", "forbidden_in_resume": ["Rust"]}
        checks = {c.name: c for c in graders.grade_tailoring(case, self.home, job_id, JD)}
        self.assertFalse(checks["resume claims none of the skills/years the user lacks"].passed)
        self.assertFalse(checks["cover letter never restates a years shortfall"].passed)


class OnboardingGraderTest(helpers.AlexHome):
    def test_invented_number_and_missing_metric_are_caught(self):
        case = CASES["onboarding"][0]
        priya = helpers.REPO / "evals" / "cases" / "priya"
        for name in ("profile.toml", "bullets.yaml"):
            shutil.copy2(priya / name, self.home / name)
        raw, answers = (priya / "resume.txt").read_text(), (priya / "questionnaire.md").read_text()
        checks = {c.name: c for c in graders.grade_onboarding(case, self.home, True, raw, answers)}
        self.assertTrue(all(c.passed for c in checks.values()),
                        [c for c in checks.values() if not c.passed])
        # Now an agent that "improved" the vague bullet and dropped a metric.
        text = (self.home / "bullets.yaml").read_text()
        text = text.replace("Improved the performance of nightly batch jobs.",
                            "Improved the performance of nightly batch jobs by 40%.")
        text = text.replace("from 61% to 78%", "significantly")
        (self.home / "bullets.yaml").write_text(text)
        checks = {c.name: c for c in graders.grade_onboarding(case, self.home, True, raw, answers)}
        self.assertFalse(checks["no bullet contains a number absent from resume and answers"].passed)
        self.assertFalse(checks["vague claim stays vague (no number invented)"].passed)
        self.assertFalse(checks["every metric from the resume was kept"].passed)


if __name__ == "__main__":
    unittest.main()
