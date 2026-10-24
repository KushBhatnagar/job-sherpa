"""Render resumes and cover letters to PDF with Typst.

Content arrives as JSON (from the tailoring playbooks); the look lives in
templates/*.typ. Typst is used through its Python package (`pip install typst`)
when installed, otherwise through the `typst` command line. Either works.

Every render also writes a Markdown copy next to the PDF, for diffing and for
pasting into application forms.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

from . import paths

FONTS = paths.TEMPLATES / "fonts"


class TypstMissing(RuntimeError):
    pass


def typst_backend() -> str | None:
    try:
        import typst  # noqa: F401
        return "python"
    except ImportError:
        pass
    return "cli" if shutil.which("typst") else None


def _compile(template: str, data: dict, out_pdf: Path) -> None:
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    src = paths.TEMPLATES / template
    payload = json.dumps(data, ensure_ascii=False)
    backend = typst_backend()
    if backend == "python":
        import typst
        typst.compile(str(src), output=str(out_pdf), root=str(paths.TEMPLATES),
                      font_paths=[str(FONTS)], ignore_system_fonts=True,
                      sys_inputs={"data": payload})
    elif backend == "cli":
        try:
            subprocess.run(["typst", "compile", "--root", str(paths.TEMPLATES),
                            "--font-path", str(FONTS), "--ignore-system-fonts",
                            "--input", f"data={payload}", str(src), str(out_pdf)],
                           check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Typst failed: {e.stderr}") from e
    else:
        raise TypstMissing("Typst is not installed. Run `pip install typst`, or install the "
                           "typst CLI (brew install typst / winget install typst / cargo install typst-cli).")


def pdf_page_count(pdf: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf.read_bytes()))


def resume_markdown(data: dict) -> str:
    c = data["contact"]
    lines = [f"# {c.get('name', '')}", "",
             " · ".join(x for x in [c.get("location"), c.get("phone"), c.get("email"), *c.get("links", [])] if x),
             "", data.get("summary", ""), "", "## Experience"]
    for org in data["experience"]:
        lines.append(f"\n**{org['org']}**")
        for role in org["roles"]:
            lines.append(f"\n*{role['title']}* — {role['dates']}")
            lines.extend(f"- {b}" for b in role["bullets"])
    if data.get("projects"):
        lines.append("\n## Projects")
        lines.extend(f"- **{p['title']}:** {p['text']}" for p in data["projects"])
    if data.get("skills"):
        lines.append("\n## Skills")
        lines.extend(f"- **{s['label']}:** {s['value']}" for s in data["skills"])
    if data.get("education"):
        lines.append("\n## Education")
        lines.extend(f"- {e['degree']} — {e.get('detail', '')}" for e in data["education"])
    if data.get("certifications"):
        lines.append("\n## Certifications")
        lines.extend(f"- {x}" for x in data["certifications"])
    if data.get("activities"):
        lines.append("\n## Activities")
        lines.extend(f"- {a}" for a in data["activities"])
    return "\n".join(lines) + "\n"


def cover_letter_markdown(data: dict) -> str:
    c = data["contact"]
    lines = [f"# {c.get('name', '')}", "", data["date"], "", data.get("greeting", "Dear Hiring Team,"), ""]
    lines += [p + "\n" for p in data["paragraphs"]]
    lines += [data.get("closing", "Sincerely,"), c.get("name", "")]
    return "\n".join(lines) + "\n"


def render(kind: str, data: dict, out_dir: Path, stem: str) -> dict:
    """kind: 'resume' | 'cover_letter'. Returns paths and the page count."""
    out_dir.mkdir(parents=True, exist_ok=True)
    md = resume_markdown(data) if kind == "resume" else cover_letter_markdown(data)
    md_path, pdf_path = out_dir / f"{stem}.md", out_dir / f"{stem}.pdf"
    md_path.write_text(md, encoding="utf-8")
    _compile("resume.typ" if kind == "resume" else "cover-letter.typ", data, pdf_path)
    return {"md": md_path, "pdf": pdf_path, "pages": pdf_page_count(pdf_path)}
