"""The user's profile (`<home>/profile.toml`) and the settings derived from it.

TOML because Python reads it with the standard library (tomllib) and people can
edit it by hand. Everything that used to be hardcoded for one person (which
titles count, which locations are reachable, the Adzuna country, the name on the
resume, the scoring thresholds) comes from here.
"""
import re
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache

from . import paths

DEFAULTS = {
    "contact": {"name": "", "location": "", "phone": "", "email": "", "links": []},
    "experience": {},
    "targets": {
        "titles": [],
        "near_miss_titles": [],
        "exclude_title_words": [],
        "locations": [],
        "remote": "anywhere",          # anywhere | allowed-regions | none
        "remote_regions": [],
        "maybe_reachable": [],
        "country_codes": [],
    },
    "search": {
        "adzuna_country": "",
        "adzuna_queries": [],
        "adzuna_where": "",
        "stale_after_days": 60,
        "hard_gate_cap": 6,
        "shortlist_min_score": 7,
        "followup_after_days": 7,
        "followup_until_days": 21,
    },
    "documents": {"paper": "a4", "one_page_resume": True, "file_name": ""},
}

# Words that, next to "remote", usually mean "remote, but only from there".
# A remote posting naming one of these is flagged restricted_remote unless the
# place is also one of the user's own locations or remote_regions.
RESTRICTING_PLACES = (
    r"u\.s\.a?|u\.k\.|\bus\b|\busa\b|united states|canada|\bcan\b|united kingdom|\buk\b|"
    r"emea|europe|\beu\b|apac|latam|americas|north america|"
    r"india|estonia|germany|netherlands|france|ireland|australia|poland|spain|italy|portugal|"
    r"brazil|mexico|colombia|argentina|japan|singapore|philippines|"
    r"california|colorado|texas|washington|virginia|maryland|delaware|"
    r"massachusetts|illinois|georgia|florida|arizona|oregon|utah|"
    r"new york|nyc|sf bay area|san francisco|seattle|chicago|atlanta|boston|"
    r"austin|denver|los angeles|portland|miami|"
    r"toronto|vancouver|montreal|ontario|british columbia|"
    r"london|berlin|amsterdam|dublin|paris|madrid|warsaw|prague|geneva|lisbon"
)
ALWAYS_MAYBE = r"anywhere|global|worldwide|distributed|flexible|work from home|\bwfh\b"


def _terms_re(terms: list[str]) -> re.Pattern | None:
    """Case-insensitive match on any of `terms`. Short terms (<=3 chars, like
    'US' or 'NYC') must stand alone as words; longer ones match anywhere."""
    parts = []
    for t in terms:
        t = t.strip()
        if not t:
            continue
        esc = re.escape(t).replace(r"\ ", r"\s+")
        parts.append(rf"\b{esc}\b" if len(t) <= 3 else esc)
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


@dataclass
class Profile:
    raw: dict
    contact: dict = field(default_factory=dict)
    targets: dict = field(default_factory=dict)
    search: dict = field(default_factory=dict)
    documents: dict = field(default_factory=dict)

    # ── titles ──
    def title_matches(self, title: str) -> bool:
        rx = _terms_re(self.targets["titles"])
        if rx is None:
            return True    # no titles set: keep everything rather than drop silently
        excl = _terms_re(self.targets["exclude_title_words"])
        return bool(rx.search(title or "")) and not (excl and excl.search(title or ""))

    def is_near_miss_title(self, title: str) -> bool:
        rx = _terms_re(self.targets["near_miss_titles"])
        excl = _terms_re(self.targets["exclude_title_words"])
        t = title or ""
        return bool(rx and rx.search(t)) and not (excl and excl.search(t)) and not self.title_matches(t)

    # ── locations ──
    def classify_location(self, location: str) -> str:
        """local | world_remote | ok_remote | restricted_remote | onsite_other"""
        loc = location or ""
        local = _terms_re(self.targets["locations"])
        is_remote = re.search(r"remote|work from home|\bwfh\b", loc, re.IGNORECASE)
        if is_remote and self.targets["remote"] != "none":
            if local and local.search(loc):
                return "ok_remote"
            regions = _terms_re(self.targets["remote_regions"])
            if regions and regions.search(loc):
                return "ok_remote"
            if re.search(RESTRICTING_PLACES, loc, re.IGNORECASE):
                return "restricted_remote"
            if self.targets["remote"] == "allowed-regions":
                return "restricted_remote"
            return "world_remote"
        if local and local.search(loc):
            return "local"
        return "onsite_other"

    def location_in_range(self, location: str) -> bool:
        """Kept by discovery: local, any remote (restricted ones are flagged, not
        dropped: the user decides), unless remote is 'none'."""
        if not self.targets["locations"] and self.targets["remote"] == "anywhere":
            return True
        return self.classify_location(location) != "onsite_other"

    def maybe_reachable(self, location: str) -> bool:
        """A dropped location that might be in range after all ('APAC', 'Distributed',
        '..., IN'). Shown in the discover report so the user can widen the profile."""
        loc = location or ""
        extra = _terms_re(self.targets["maybe_reachable"])
        if re.search(ALWAYS_MAYBE, loc, re.IGNORECASE) or (extra and extra.search(loc)):
            return True
        codes = [c.strip() for c in self.targets["country_codes"] if c.strip()]
        # A trailing country code ("Bengaluru, IN"), case-sensitive so the word
        # "In-Office" doesn't count.
        return any(re.search(rf"(?:^|[,\s]){re.escape(c)}$", loc.strip()) for c in codes)

    @property
    def name(self) -> str:
        return self.contact.get("name") or "Your Name"

    def file_stem(self, kind: str) -> str:
        base = self.documents.get("file_name") or self.name
        return f"{base}_{kind}"


def _merge(defaults: dict, given: dict) -> dict:
    out = {}
    for key, value in defaults.items():
        if isinstance(value, dict):
            out[key] = {**value, **(given.get(key) or {})}
        else:
            out[key] = given.get(key, value)
    for key, value in given.items():
        out.setdefault(key, value)
    return out


def from_dict(data: dict) -> Profile:
    merged = _merge(DEFAULTS, data)
    return Profile(raw=merged, contact=merged["contact"], targets=merged["targets"],
                   search=merged["search"], documents=merged["documents"])


@lru_cache(maxsize=None)
def _load(path_str: str, mtime: float) -> Profile:
    with open(path_str, "rb") as f:
        return from_dict(tomllib.load(f))


def load() -> Profile:
    """The current profile, or defaults (keep everything) when none exists yet."""
    path = paths.profile_path()
    if not path.exists():
        return from_dict({})
    return _load(str(path), path.stat().st_mtime)
