"""Filtering and de-duplication shared by every source.

Each source adapter returns postings in one common shape (source, title,
location, url, description, posted_at, source_job_id, raw_json). What counts as
a relevant title or a reachable location comes from the user's profile
(`profile.Profile`); this module only uses it.
"""
import difflib

from .profile import Profile

# A posting stored under several locations keeps them joined with this.
LOCATION_SEP = " / "

# Which posting of a multi-location group becomes the stored row: the one the
# user would most likely apply through.
_RANK = {"local": 0, "ok_remote": 1, "world_remote": 2, "restricted_remote": 3, "onsite_other": 4}

SAME_JD_RATIO = 0.9
# Only full JDs can prove two postings are one job. Aggregator excerpts (~500
# chars) are often just the employer's boilerplate intro, which made two
# different jobs in two cities look identical (0.96) during testing.
MIN_JD_CHARS = 600


def _title_key(title: str) -> str:
    return " ".join((title or "").lower().split())


def same_jd(a: str | None, b: str | None) -> bool:
    """True when two JDs are near-identical: the same job posted twice.
    Missing or short JDs never match, so unknown postings stay separate."""
    a, b = (a or "")[:3000], (b or "")[:3000]
    if len(a) < MIN_JD_CHARS or len(b) < MIN_JD_CHARS:
        return False
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sm.quick_ratio() >= SAME_JD_RATIO and sm.ratio() >= SAME_JD_RATIO


def merge_multi_location(jobs: list[dict], profile: Profile, company_key=lambda j: "") -> list[dict]:
    """Collapse postings with the same company, title AND near-identical JD into one
    row, locations joined. Same title alone is not enough: same-titled postings in
    different cities are often different jobs (JD similarity 0.16-0.44 in testing),
    while real per-country copies scored 1.0.

    Each merged dict gets `merged_count` (1 when nothing was merged)."""
    by_title: dict[tuple, list[dict]] = {}
    for j in jobs:
        by_title.setdefault((company_key(j), _title_key(j["title"])), []).append(j)
    groups: list[list[dict]] = []
    for same_title in by_title.values():
        clusters: list[list[dict]] = []
        for j in same_title:
            home = next((c for c in clusters if same_jd(c[0].get("description"), j.get("description"))), None)
            if home:
                home.append(j)
            else:
                clusters.append([j])
        groups.extend(clusters)
    out = []
    for group in groups:
        group = sorted(group, key=lambda j: _RANK[profile.classify_location(j["location"])])
        locs: list[str] = []
        for j in group:
            for part in (j["location"] or "").split(LOCATION_SEP):
                part = part.strip()
                if part and part.lower() not in (x.lower() for x in locs):
                    locs.append(part)
        merged = dict(group[0])
        merged["location"] = LOCATION_SEP.join(locs)
        merged["remote_type"] = profile.classify_location(group[0]["location"])
        merged["merged_count"] = len(group)
        out.append(merged)
    return out
