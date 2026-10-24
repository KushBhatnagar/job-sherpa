"""Adzuna job-search API adapter (free tier, ~1000 calls/month).

Needs ADZUNA_APP_ID and ADZUNA_APP_KEY in `.env` (free signup: developer.adzuna.com),
and `search.adzuna_country` in profile.toml (a two-letter code Adzuna supports:
gb, us, in, de, fr, nl, au, ca, sg, ...).

Unlike the company boards, this is one broad keyword sweep across every employer.
Descriptions are ~500-character excerpts, so these jobs are flagged
`needs_full_jd` and never scored until the real JD is found.
"""
import json
import urllib.parse

from ..config import load_env
from ._http import get_json

SOURCE = "adzuna"


class MissingCredentials(Exception):
    pass


def fetch(country: str, query: str, where: str = "", max_days_old: int = 7) -> list[dict]:
    env = load_env()
    app_id, app_key = env.get("ADZUNA_APP_ID"), env.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise MissingCredentials("ADZUNA_APP_ID / ADZUNA_APP_KEY not set (see .env.example)")
    if not country:
        raise MissingCredentials("search.adzuna_country is not set in profile.toml")

    params = {"app_id": app_id, "app_key": app_key, "results_per_page": 50, "what": query,
              "max_days_old": max_days_old, "content-type": "application/json"}
    if where:
        params["where"] = where
    url = (f"https://api.adzuna.com/v1/api/jobs/{country.lower()}/search/1?"
           f"{urllib.parse.urlencode(params)}")
    data = get_json(url)

    jobs = []
    for j in data.get("results", []):
        jobs.append({
            "source": SOURCE,
            "source_job_id": str(j.get("id", "")),
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("display_name", ""),
            # The real employer, never a shared placeholder: otherwise different
            # employers' same-titled postings collide under one dedup hash.
            "company_name": (j.get("company") or {}).get("display_name", "") or "(unknown employer)",
            "url": j.get("redirect_url", ""),
            "description": j.get("description", ""),
            "posted_at": (j.get("created") or "")[:10] or None,
            "raw_json": json.dumps(j),
        })
    return jobs
