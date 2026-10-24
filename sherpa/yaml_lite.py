"""Reads exactly one YAML shape: a top-level list of flat `key: value` records.

    - id: b-001
      text: "Cut onboarding time by 60% for 10+ teams"
      tags: platform, api-design

That is all `bullets.yaml` and `companies.yaml` need, and it keeps Job Sherpa free
of dependencies (no pyyaml). Rules, matching real YAML where it matters:
  - `#` starts a comment only at the start of a line or after a space;
  - values may be wrapped in "double" or 'single' quotes, and then may contain
    ` #` and `: ` safely;
  - no nesting, no multi-line values. Lists are comma-separated strings.
"""
from pathlib import Path


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'" and (i == 0 or line[i - 1] in " :"):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace('\\"', '"') if value[0] == '"' else inner.replace("''", "'")
    return value


def loads_flat_list(text: str) -> list[dict]:
    items: list[dict] = []
    current: dict | None = None
    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("- "):
            if current is not None:
                items.append(current)
            current = {}
            line = "  " + line.lstrip()[2:]
        if current is None:
            continue
        if ":" in line:
            key, _, val = line.strip().partition(":")
            current[key.strip()] = _unquote(val)
    if current is not None:
        items.append(current)
    return items


def load_flat_list(path: Path) -> list[dict]:
    return loads_flat_list(Path(path).read_text(encoding="utf-8"))


def split_list(value: str) -> list[str]:
    """'a, b, c' -> ['a', 'b', 'c']"""
    return [v.strip() for v in (value or "").split(",") if v.strip()]
