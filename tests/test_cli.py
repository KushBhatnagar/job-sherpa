import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers
from sherpa import cli, db, render

JD = ("Senior Backend Engineer, Berlin. You will own our event-driven order platform. "
      "Requirements: 5+ years of backend experience with Go or Python, Kafka, PostgreSQL. ") * 4


class InitTest(unittest.TestCase):
    def test_init_creates_private_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "me"
            with mock.patch.dict(os.environ, {"SHERPA_HOME": str(home)}):
                helpers.AlexHome.run_cli(self, "init")
                for name in ("profile.toml", "bullets.yaml", "master-resume.json", "companies.yaml",
                             "stories.md", "screening-answers.md", "sherpa.db"):
                    self.assertTrue((home / name).exists(), name)
                (home / "profile.toml").write_text("# mine\n")
                helpers.AlexHome.run_cli(self, "init")        # never overwrites
                self.assertEqual((home / "profile.toml").read_text(), "# mine\n")


class WorkflowTest(helpers.AlexHome):
    def add_job(self, jd=JD):
        out = self.run_cli("add-job", "--company", "Example Freight", "--title", "Senior Backend Engineer",
                           "--location", "Berlin, Germany", "--file", "-", stdin=jd)
        self.assertIn("job #1", out)

    def test_score_rules(self):
        self.add_job()
        with self.assertRaises(SystemExit):     # hard blocker caps the score at 6
            self.run_cli("score", "1", "--score", "9", "--json", '{"hard_blockers": ["10+ years"]}')
        self.assertIn("scored 6/10", self.run_cli("score", "1", "--score", "6", "--json",
                                                  '{"hard_blockers": ["10+ years"]}'))

    def test_no_score_without_full_jd(self):
        self.add_job(jd="Too short to be a real JD.")
        with self.assertRaises(SystemExit):
            self.run_cli("score", "1", "--score", "8")
        self.run_cli("set-jd", "1", stdin=JD)
        self.assertIn("scored 8/10", self.run_cli("score", "1", "--score", "8", "--json", '{"angle": "x"}'))

    def test_shortlist_apply_log_stats(self):
        self.add_job()
        self.run_cli("score", "1", "--score", "8", "--json", '{"angle": "Lead with the redesign"}')
        self.assertIn("(1 jobs)", self.run_cli("shortlist-export"))
        self.run_cli("apply", "--job-id", "1", "--channel", "portal")
        self.run_cli("log", "1", "--event", "rejected", "--notes", "years")
        conn = db.connect()
        app = conn.execute("SELECT status, rejection_reason FROM applications WHERE id = 1").fetchone()
        self.assertEqual((app["status"], app["rejection_reason"]), ("rejected", "years"))

    def test_applications_lists_ids_and_last_event(self):
        self.add_job()
        self.run_cli("apply", "--job-id", "1", "--date", "2026-10-01")
        self.run_cli("log", "1", "--event", "recruiter_screen", "--date", "2026-10-05")
        out = self.run_cli("applications")
        self.assertIn("Example Freight", out)
        self.assertIn("recruiter_screen 2026-10-05", out)
        self.run_cli("log", "1", "--event", "rejected", "--date", "2026-10-09")
        self.assertIn("No matching applications", self.run_cli("applications"))   # closed ones hidden
        self.assertIn("rejected 2026-10-09", self.run_cli("applications", "--all"))
        self.assertIn("Example Freight", self.run_cli("applications", "--company", "freight", "--all"))

    def test_discover_filters_and_reports(self):
        (self.home / "companies.yaml").write_text("- name: Example Freight\n  ats_type: greenhouse\n  ats_token: x\n")
        fake = [
            {"title": "Senior Backend Engineer", "location": "Berlin, Germany"},
            {"title": "Backend Engineer", "location": "Remote - EMEA"},
            {"title": "Backend Engineer", "location": "Potsdam, Brandenburg"},     # dropped, worth a look
            {"title": "Engineering Manager", "location": "Berlin"},                # near miss
            {"title": "Frontend Engineer", "location": "Berlin"},                  # excluded word
        ]
        jobs = [dict(source="greenhouse", source_job_id=str(i), url="u", description=JD, posted_at=None,
                     raw_json="{}", **j) for i, j in enumerate(fake)]
        with mock.patch.dict(cli.ATS_ADAPTERS, {"greenhouse": lambda token: jobs}):
            out = self.run_cli("discover", "--source", "greenhouse")
        self.assertIn("2 new job(s)", out)
        self.assertIn("worth a look", out)
        self.assertIn("Engineering Manager", out)

    def test_every_source_failing_is_not_a_quiet_day(self):
        (self.home / "companies.yaml").write_text("- name: A\n  ats_type: lever\n  ats_token: a\n")

        def boom(token):
            raise OSError("network down")
        with mock.patch.dict(cli.ATS_ADAPTERS, {"lever": boom}):
            with self.assertRaises(SystemExit):
                self.run_cli("discover", "--source", "lever")


@unittest.skipUnless(render.typst_backend(), "Typst not installed")
class RenderTest(helpers.AlexHome):
    def test_master_documents_render_on_one_page(self):
        self.assertIn("(1 page)", self.run_cli("master-resume"))
        self.assertIn("(1 page)", self.run_cli("master-cover-letter"))

    def test_tailor_resume_blocks_invented_claims(self):
        self.run_cli("add-job", "--company", "Example Freight", "--title", "Backend Engineer", "--file", "-", stdin=JD)
        payload = json.loads((self.home / "master-resume.json").read_text())
        payload["experience"][0]["roles"][0]["bullets"] = ["b-001", {"id": "b-002", "text": "Cut incidents by 90%"}]
        bad = self.home / "bad.json"
        bad.write_text(json.dumps(payload))
        with self.assertRaises(SystemExit):
            self.run_cli("tailor-resume", "1", "--data", str(bad))
        payload["experience"][0]["roles"][0]["bullets"] = ["b-001", "b-002"]
        bad.write_text(json.dumps(payload))
        out = self.run_cli("tailor-resume", "1", "--data", str(bad))
        self.assertIn("(1 page)", out)
        self.assertEqual(len(list((self.home / "drafts").glob("1__*/*.pdf"))), 1)


if __name__ == "__main__":
    unittest.main()
