"""Check every companies.yaml entry against its live board.

Why: a company listed on the wrong ATS fails quietly. Discovery catches the
error, prints one line, and that company is simply never seen again.

Each entry lands in one of three buckets:
  ok       board answered and returned postings
  empty    board answered with zero postings: a quiet board, or the wrong token
           pointing at someone else's real board
  broken   board didn't answer (404/error): the token or ATS type is wrong

For anything not ok, the other ATSes are probed to suggest what the row should
say. Suggestions are never applied automatically: a wrong "fix" hides a company
just as well as a wrong original.
"""
from concurrent.futures import ThreadPoolExecutor

from . import enrich, paths, yaml_lite


def _count(ats: str, token: str, _retry: bool = True) -> tuple[str, int, str]:
    try:
        jobs = enrich.ADAPTERS[ats](token)
        return ("ok" if jobs else "empty"), len(jobs), ""
    except KeyError:
        return "broken", 0, f"unknown ats_type {ats!r}"
    except Exception as e:
        # One retry: a read timeout is usually the network, not a wrong token.
        if _retry and "timed out" in repr(e).lower():
            return _count(ats, token, _retry=False)
        return "broken", 0, repr(e)[:80]


def _suggest(company: str, current: tuple[str, str]) -> list[str]:
    out = []
    for ats, token in enrich.board_candidates(company):
        if (ats, token) == current:
            continue
        status, count, _ = _count(ats, token)
        if status == "ok":
            out.append(f"{ats}:{token} ({count} postings)")
    return out


def audit(rows: list[dict] | None = None, workers: int = 8) -> list[dict]:
    if rows is None:
        rows = yaml_lite.load_flat_list(paths.companies_path())
    rows = [r for r in rows if r.get("ats_type") and r.get("ats_token")]

    def check(row):
        status, count, detail = _count(row["ats_type"], row["ats_token"])
        result = {"name": row["name"], "ats": row["ats_type"], "token": row["ats_token"],
                  "status": status, "count": count, "detail": detail, "suggestions": []}
        if status != "ok":
            result["suggestions"] = _suggest(row["name"], (row["ats_type"], row["ats_token"]))
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(check, rows))
