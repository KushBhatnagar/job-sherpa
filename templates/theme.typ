// Shared look for the resume and cover letter, so the two read as one set:
// Source Sans 3 (OFL, bundled in fonts/), monochrome text, grey meta, thin rules.
//
// Ligatures are OFF on purpose: with them on, PDF text extraction drops letters
// ("Microsof", "ofice"), which hurts ATS keyword matching. Keep them off.

#let colors = (
  text: rgb("#1c1c1c"),
  meta: rgb("#555555"),
  contact: rgb("#444444"),
  rule: rgb("#d6d6d6"),
)

#let base(body) = {
  set text(font: "Source Sans 3", fill: colors.text, ligatures: false, discretionary-ligatures: false,
           hyphenate: false, lang: "en")
  set par(justify: false)
  body
}

#let header(contact, gap-after: 5pt) = {
  // No negative tracking on the name: it made PDF text extraction split it.
  block(below: 6pt, text(size: 20.5pt, weight: 700, contact.name))
  let items = (contact.at("location", default: ""), contact.at("phone", default: ""),
               contact.at("email", default: "")) + contact.at("links", default: ())
  // Each item is a box so it wraps whole, never mid-URL.
  block(above: 0pt, text(size: 9.8pt, fill: colors.contact,
    items.filter(x => x != "").map(x => box(x)).join(h(14pt))))
  v(gap-after)
}

#let rule() = line(length: 100%, stroke: 0.75pt + colors.rule)
