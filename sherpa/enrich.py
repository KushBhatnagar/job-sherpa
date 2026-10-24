"""Find the real job description for jobs that arrived without one.

Adzuna gives a 500-character excerpt; a job you add by hand may have only a link.
Both are flagged `needs_full_jd` so score-fit never scores them blind.

This looks the same posting up on the company's OWN public board (Greenhouse /
Lever / Ashby / SmartRecruiters, the APIs `sherpa discover` already reads), which
serves the complete JD. It never fetches LinkedIn, Naukri or any site that
forbids it.

The danger is a confident match on the WRONG posting: a company can have three
"Staff PM" roles open. So a match is only accepted when the title matches exactly
after normalization, or closely AND the locations agree. Everything else is
reported as unresolved for the user to decide, never guessed at.
"""
import re
from difflib import SequenceMatcher

from . import paths, profile, yaml_lite
from .sources import ashby, greenhouse, lever, smartrecruiters
from .sources._http import get_json

ADAPTERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
}

# Legal/marketing suffixes that are in the company name but never in the board slug.
_NOISE = {"inc", "inc.", "llc", "ltd", "ltd.", "limited", "pvt", "pvt.", "private",
          "corp", "corporation", "co", "company", "technologies", "technology",
          "solutions", "systems", "labs", "software", "services", "consulting",
          "group", "global", "the"}

_CACHE: dict[tuple[str, str], list[dict] | None] = {}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _norm_title(title: str) -> str:
    """Lowercase, punctuation out, '&'/'and' unified. Seniority words are KEPT —
    'Staff PM' and 'Senior PM' are different jobs."""
    t = (title or "").lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return " ".join(t.split())


def _title_similarity(a: str, b: str) -> float:
    ta, tb = set(_norm_title(a).split()), set(_norm_title(b).split())
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    # SequenceMatcher catches word-order and abbreviation differences Jaccard misses.
    return max(jaccard, SequenceMatcher(None, _norm_title(a), _norm_title(b)).ratio())


def _company_key(name: str) -> str:
    """'Acme Inc.' and 'Acme' must hit the same watchlist row: aggregators carry
    the legal name, companies.yaml carries the short one."""
    words = [w for w in _norm_title(name).split() if w not in _NOISE]
    return "-".join(words or _norm_title(name).split())


def _watchlist() -> dict[str, tuple[str, str]]:
    """company name (normalized) -> (ats_type, ats_token) from companies.yaml."""
    out = {}
    path = paths.companies_path()
    if path.exists():
        for row in yaml_lite.load_flat_list(path):
            if row.get("ats_type") and row.get("ats_token"):
                out[_company_key(row["name"])] = (row["ats_type"], row["ats_token"])
    return out


def board_candidates(company: str) -> list[tuple[str, str]]:
    """(ats_type, token) pairs worth trying for this company, best guess first."""
    known = _watchlist().get(_company_key(company))

    words = [w for w in _norm_title(company).split() if w not in _NOISE]
    if not words:
        words = _norm_title(company).split()
    tokens = []
    for candidate in ("".join(words), "-".join(words), words[0] if words else ""):
        if candidate and candidate not in tokens:
            tokens.append(candidate)
    guesses = [(ats, tok) for tok in tokens for ats in ADAPTERS]
    # The watchlist token goes first, but is NOT the only try: a stale or wrong
    # entry there must not block the guessed boards (a company listed on the
    # wrong ATS once hid its real board for weeks).
    return ([known] + [g for g in guesses if g != known]) if known else guesses


def _board_jobs(ats: str, token: str) -> list[dict] | None:
    """None means that board doesn't exist / isn't reachable, which is not the
    same as 'exists but has no matching job'."""
    key = (ats, token)
    if key not in _CACHE:
        try:
            _CACHE[key] = ADAPTERS[ats](token)
        except Exception:
            _CACHE[key] = None
    return _CACHE[key]


def _city_match(alert_loc: str, board_loc: str) -> bool:
    """Same city named in both. Breaks ties when a company has the same title open
    in several cities: picking the wrong one would attach the wrong JD."""
    a = {_ALIASES.get(w, w) for w in _norm_title(alert_loc).split()} - _GENERIC_PLACE_WORDS
    b = {_ALIASES.get(w, w) for w in _norm_title(board_loc).split()} - _GENERIC_PLACE_WORDS
    return bool(a & b)


# Cities known under two spellings. Add yours by pull request.
_ALIASES = {"bangalore": "bengaluru", "gurgaon": "gurugram", "bombay": "mumbai",
            "madras": "chennai", "calcutta": "kolkata", "nyc": "new york", "munchen": "munich",
            "muenchen": "munich"}
_GENERIC_PLACE_WORDS = {"in", "hybrid", "remote", "office", "on", "site", "onsite"}


def _hydrate(ats: str, job: dict) -> dict:
    """SmartRecruiters' list endpoint returns no description (see its adapter) —
    fetch the one posting we actually matched."""
    if ats != "smartrecruiters" or job.get("description"):
        return job
    try:
        data = get_json(f"https://api.smartrecruiters.com/v1/companies/"
                        f"{job['_token']}/postings/{job['source_job_id']}")
        sections = (data.get("jobAd") or {}).get("sections") or {}
        parts = [_html_to_text(v.get("text")) for v in sections.values() if isinstance(v, dict)]
        # job['url'] from the list endpoint is the API ref; swap in the page a human can open.
        job = dict(job, description="\n\n".join(p for p in parts if p),
                   url=(data.get("applyUrl") or data.get("postingUrl")
                        or f"https://jobs.smartrecruiters.com/{job['_token']}/{job['source_job_id']}"))
    except Exception:
        pass
    return job


def _html_to_text(raw: str | None) -> str:
    import html as html_mod
    text = html_mod.unescape(html_mod.unescape(raw or ""))
    text = re.sub(r"<(br|/p|/li|/h\d|li)[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def _locations_agree(alert_loc: str, board_loc: str) -> bool:
    """Both in the user's range, or the same kind of place. An unknown location
    can't disagree."""
    if not alert_loc or alert_loc.startswith("(unknown"):
        return True
    p = profile.load()
    a, b = p.classify_location(alert_loc), p.classify_location(board_loc)
    reachable = {"local", "ok_remote", "world_remote"}
    return a == b or {a, b} <= reachable


def find_posting(company: str, title: str, location: str) -> dict:
    """Look for this job on the company's public board.

    Returns {"status": "matched"|"unresolved", ...}. "matched" carries the full
    posting; "unresolved" carries why, plus any near-misses worth eyeballing.
    """
    candidates, near_misses, boards_seen = [], [], []
    for ats, token in board_candidates(company):
        jobs = _board_jobs(ats, token)
        if not jobs:
            continue
        boards_seen.append(f"{ats}:{token}")
        for job in jobs:
            score = _title_similarity(title, job.get("title", ""))
            if score < 0.5:
                continue
            exact = _norm_title(title) == _norm_title(job.get("title", ""))
            same_place = _locations_agree(location, job.get("location", ""))
            if exact or (score >= 0.75 and same_place):
                candidates.append({"rank": (exact, _city_match(location, job.get("location", "")), score),
                                   "job": dict(job, _token=token), "ats": ats, "exact": exact,
                                   "score": score, "board": f"{ats}:{token}"})
            else:
                near_misses.append((score, f"{job.get('title')} [{job.get('location')}] ({ats}:{token})"))

    candidates.sort(key=lambda c: c["rank"], reverse=True)
    if candidates:
        best = candidates[0]
        tied = [c for c in candidates[1:] if c["rank"] == best["rank"]
                and c["job"].get("url") != best["job"].get("url")]
        if tied:
            # Two postings fit equally well (same title, different city). Guessing
            # here is how the wrong JD gets attached — hand it back instead.
            others = [f"{c['job'].get('title')} [{c['job'].get('location')}] {c['job'].get('url', '')}"
                      for c in [best] + tied][:4]
            return {"status": "unresolved",
                    "reason": f"{len(tied) + 1} postings matched equally well — can't tell which",
                    "boards_seen": boards_seen, "near_misses": others}
        posting = _hydrate(best["ats"], best["job"])
        if (posting.get("description") or "").strip():
            return {"status": "matched", "posting": posting, "board": best["board"],
                    "confidence": "exact title" if best["exact"] else f"title {best['score']:.0%} + location",
                    "similarity": best["score"]}
        near_misses.append((best["score"], f"{posting.get('title')} [{posting.get('location')}] "
                                           f"({best['board']}) — board returned no description"))

    near_misses.sort(reverse=True)
    return {"status": "unresolved",
            "reason": ("no public board found for this company" if not boards_seen
                       else "board found, but no posting matched confidently"),
            "boards_seen": boards_seen,
            "near_misses": [n for _, n in near_misses[:3]]}
