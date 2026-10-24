import unittest

import helpers  # noqa: F401  (sets sys.path)
from sherpa import claims, db, normalize, profile, yaml_lite


class YamlLiteTest(unittest.TestCase):
    def test_records_comments_and_quotes(self):
        rows = yaml_lite.loads_flat_list(
            "# header\n"
            "- id: b-001\n"
            "  text: Cut latency by 40% # trailing comment\n"
            "  tags: go, kafka\n"
            "- id: b-002\n"
            '  text: "Ranked #1 of 30: a quoted value keeps its # and colon"\n'
            "  notes: C# services\n")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["text"], "Cut latency by 40%")
        self.assertEqual(yaml_lite.split_list(rows[0]["tags"]), ["go", "kafka"])
        self.assertEqual(rows[1]["text"], "Ranked #1 of 30: a quoted value keeps its # and colon")
        self.assertEqual(rows[1]["notes"], "C# services")


def _alex():
    return profile.from_dict({
        "targets": {"titles": ["backend engineer", "software engineer"],
                    "near_miss_titles": ["engineering manager"],
                    "exclude_title_words": ["intern", "frontend"],
                    "locations": ["berlin", "germany"], "remote": "allowed-regions",
                    "remote_regions": ["emea", "europe"], "maybe_reachable": ["brandenburg"],
                    "country_codes": ["DE"]}})


class ProfileTest(unittest.TestCase):
    def test_titles(self):
        p = _alex()
        self.assertTrue(p.title_matches("Senior Backend Engineer"))
        self.assertFalse(p.title_matches("Backend Engineer Intern"))
        self.assertFalse(p.title_matches("Product Manager"))
        self.assertTrue(p.is_near_miss_title("Engineering Manager, Payments"))

    def test_locations_allowed_regions(self):
        p = _alex()
        self.assertEqual(p.classify_location("Berlin, Germany"), "local")
        self.assertEqual(p.classify_location("Remote - EMEA"), "ok_remote")
        self.assertEqual(p.classify_location("Remote, Germany"), "ok_remote")
        self.assertEqual(p.classify_location("Remote - U.S."), "restricted_remote")
        self.assertEqual(p.classify_location("Remote"), "restricted_remote")   # only regions allowed
        self.assertEqual(p.classify_location("San Francisco, CA"), "onsite_other")
        self.assertFalse(p.location_in_range("New York, NY"))
        self.assertTrue(p.maybe_reachable("Potsdam, Brandenburg"))
        self.assertTrue(p.maybe_reachable("Hamburg, DE"))
        self.assertFalse(p.maybe_reachable("In-Office, Paris"))

    def test_locations_anywhere(self):
        p = profile.from_dict({"targets": {"locations": ["bengaluru", "bangalore", "india"]}})
        self.assertEqual(p.classify_location("Remote"), "world_remote")
        self.assertEqual(p.classify_location("Remote - India"), "ok_remote")
        self.assertEqual(p.classify_location("Remote, US"), "restricted_remote")
        self.assertEqual(p.classify_location("Bangalore, Karnataka"), "local")

    def test_empty_profile_keeps_everything(self):
        p = profile.from_dict({})
        self.assertTrue(p.title_matches("Anything"))
        self.assertTrue(p.location_in_range("Anywhere at all"))


LONG_JD = "We build logistics software. " * 40


class NormalizeTest(unittest.TestCase):
    def test_merges_same_job_posted_in_several_countries(self):
        jobs = [{"title": "Backend Engineer", "location": "Paris, France", "description": LONG_JD},
                {"title": "Backend Engineer", "location": "Berlin, Germany", "description": LONG_JD}]
        merged = normalize.merge_multi_location(jobs, _alex())
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["location"], "Berlin, Germany / Paris, France")  # reachable one first
        self.assertEqual(merged[0]["merged_count"], 2)

    def test_same_title_different_jd_stays_separate(self):
        jobs = [{"title": "Backend Engineer", "location": "Berlin", "description": LONG_JD},
                {"title": "Backend Engineer", "location": "Munich", "description": "Payments team. " * 60}]
        self.assertEqual(len(normalize.merge_multi_location(jobs, _alex())), 2)


class DbTest(helpers.AlexHome):
    def test_rediscovery_with_new_country_is_not_a_duplicate(self):
        conn = db.connect()
        cid = db.get_or_create_company(conn, "Example Co")
        first, new1 = db.upsert_discovered_job(conn, company_id=cid, source="greenhouse", title="Backend Engineer",
                                               location="Berlin / Paris", url="u", description=LONG_JD)
        again, new2 = db.upsert_discovered_job(conn, company_id=cid, source="greenhouse", title="Backend Engineer",
                                               location="Berlin / Paris / Madrid", url="u", description=LONG_JD)
        self.assertTrue(new1)
        self.assertFalse(new2)
        self.assertEqual(first, again)


class ClaimsTest(helpers.AlexHome):
    def test_verbatim_and_reworded(self):
        bullets = claims.load_bullets()
        r = claims.Resolved()
        self.assertEqual(claims.resolve_bullet("b-009", bullets, r, "x"), bullets["b-009"]["text"])
        claims.resolve_bullet({"id": "b-002", "text": "Introduced contract tests across 14 services, "
                                                    "cutting integration incidents by 35%."}, bullets, r, "x")
        self.assertEqual(r.errors, [])
        self.assertEqual(r.used_ids, ["b-009", "b-002"])

    def test_invented_number_untraceable_line_and_unknown_id(self):
        bullets = claims.load_bullets()
        r = claims.Resolved()
        claims.resolve_bullet({"id": "b-002", "text": "Cut incidents by 60% across 14 services"}, bullets, r, "x")
        claims.resolve_bullet("Led a team of 12", bullets, r, "x")
        claims.resolve_bullet({"id": "b-999", "text": "anything"}, bullets, r, "x")
        self.assertEqual(len(r.errors), 3)
        self.assertIn("60", r.errors[0])

    def test_summary_numbers_must_exist(self):
        bullets = claims.load_bullets()
        r = claims.Resolved()
        claims.check_free_text("8 years, 22 carriers", bullets, "total_years = 8", r, "summary")
        self.assertEqual(r.errors, [])
        claims.check_free_text("10 years", bullets, "total_years = 8", r, "summary")
        self.assertEqual(len(r.errors), 1)
        r2 = claims.Resolved()
        claims.check_free_text("your 3 million users", bullets, "", r2, "letter", job_description="3 million users")
        self.assertEqual(r2.errors, [])


class TemplateTest(unittest.TestCase):
    def test_no_letter_spacing_or_ligatures(self):
        """Letter-spacing splits words in extracted text ("S K I L LS") and
        ligatures drop letters ("Microsof"); an ATS reads the extracted text."""
        for name in ("theme.typ", "resume.typ", "cover-letter.typ"):
            code = "\n".join(line.split("//")[0] for line in
                             (helpers.REPO / "templates" / name).read_text().splitlines())
            self.assertNotIn("tracking:", code, name)
        self.assertIn("ligatures: false", (helpers.REPO / "templates" / "theme.typ").read_text())


if __name__ == "__main__":
    unittest.main()
