// Resume template. Content comes from JSON passed in as `--input data=...`
// (sherpa/render.py does this); this file only decides how it looks.
#import "theme.typ": base, header, colors, rule

#let data = json(bytes(sys.inputs.data))
#let body-size = 9.8pt

#set document(title: data.contact.name + " - Resume", author: data.contact.name)
#set page(paper: data.at("paper", default: "a4"),
          margin: (top: 36pt, bottom: 32pt, left: 36pt, right: 36pt))
#show: base
#set text(size: body-size)
#set par(leading: 0.48em, spacing: 0.5em)

#let section(title) = {
  v(7pt)
  // Heading, a small gap, then the rule: the rule must never touch the letters.
  // No letter-spacing: it makes text extraction (what an ATS reads) split
  // headings into "S K I L LS".
  block(sticky: true, below: 6pt, {
    block(below: 3.5pt, text(size: 9.6pt, weight: 700, upper(title)))
    rule()
  })
}

#let role-header(title, dates) = block(sticky: true, above: 4pt, below: 3pt,
  grid(columns: (1fr, auto), column-gutter: 12pt,
    text(size: body-size + 0.3pt, weight: 600, title),
    text(size: body-size - 0.3pt, fill: colors.meta, dates)))

#let bullet-item(t) = block(above: 3pt, below: 3pt, breakable: false,
  grid(columns: (11pt, 1fr), [•], t))

// ── Header + summary ──
#header(data.contact)
#if data.at("summary", default: "") != "" {
  text(size: body-size + 0.3pt, data.summary)
}

// ── Experience ──
#section("Experience")
#for (i, org) in data.experience.enumerate() {
  if i > 0 { v(3pt) }
  block(sticky: true, below: 3pt, text(size: 11.2pt, weight: 700, org.org))
  for (j, role) in org.roles.enumerate() {
    if j > 0 { v(3pt) }
    role-header(role.title, role.dates)
    for b in role.bullets { bullet-item(b) }
  }
}

// ── Projects (optional) ──
#if data.at("projects", default: ()).len() > 0 {
  section("Projects")
  for p in data.projects {
    block(above: 3pt, below: 3pt, [#text(weight: 600, p.title + ":")#h(4pt)#p.text])
  }
}

// ── Skills ──
#if data.at("skills", default: ()).len() > 0 {
  section("Skills")
  grid(columns: (auto, 1fr), column-gutter: 14pt, row-gutter: 5pt,
    ..data.skills.map(s => (text(weight: 600, s.label.trim(":", at: end)), s.value)).flatten())
}

// ── Education & certifications ──
#let certs = data.at("certifications", default: ())
#if data.at("education", default: ()).len() > 0 or certs.len() > 0 {
  section(if certs.len() > 0 { "Education & Certifications" } else { "Education" })
  for e in data.at("education", default: ()) {
    block(above: 3pt, below: 3pt,
      [#text(weight: 600, e.degree)#h(10pt)#text(size: body-size - 0.3pt, fill: colors.meta,
        e.at("detail", default: ""))])
  }
  if certs.len() > 0 { block(above: 4pt, certs.join("  ·  ")) }
}

// ── Activities (optional) ──
#if data.at("activities", default: ()).len() > 0 {
  section("Activities")
  for a in data.activities { block(above: 3pt, below: 3pt, a) }
}
