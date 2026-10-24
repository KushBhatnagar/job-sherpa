// Source of docs/how-it-works.png. Re-render after editing:
//   python3 -c "import typst; typst.compile('docs/how-it-works.typ', output='docs/how-it-works.png', ppi=200, font_paths=['templates/fonts'])"
#set page(width: 860pt, height: auto, margin: 18pt, fill: white)
#set text(font: "Source Sans 3", size: 12pt, fill: rgb("#1c1c1c"), ligatures: false)

#let accent = rgb("#0a7a96")
#let soft = rgb("#eaf6fa")
#let grey = rgb("#555555")

#let card(title, body, fill: white, width: 100%) = box(width: width,
  stroke: 1pt + accent, radius: 6pt, inset: 9pt, fill: fill,
  [#text(weight: 700, size: 13pt, title) \ #text(size: 10.5pt, fill: grey, body)])

#let step(n, title, body) = card(
  [#box(fill: accent, radius: 9pt, inset: (x: 5pt, y: 2pt), text(fill: white, size: 10pt, weight: 700, str(n)))  #title],
  body)

#let right-arrow = align(center + horizon, text(size: 20pt, fill: accent, sym.arrow.r))
#let left-arrow = align(center + horizon, text(size: 20pt, fill: accent, sym.arrow.l))
#let down-arrow(label: none) = align(center, text(size: 18pt, fill: accent, sym.arrow.b) +
  if label != none { h(6pt) + text(size: 10pt, fill: grey, label) })

#align(center, text(size: 20pt, weight: 700)[How Job Sherpa works])
#v(4pt)

#block(width: 100%, stroke: (paint: grey, thickness: 1pt, dash: "dashed"), radius: 8pt, inset: 14pt, {
  text(size: 11pt, fill: grey, weight: 600)[ON YOUR COMPUTER · Job Sherpa has no server and no account: your data stays in your folder]
  v(6pt)
  grid(columns: (1fr, 1fr), column-gutter: 16pt,
    grid(columns: (1fr, 1fr), column-gutter: 10pt,
      card([Your resume], [PDF, Word or text]),
      card([Your answers], [a guided questionnaire])),
    card([Your coding agent, or you], [Claude Code, Codex, Cursor... follow the playbooks. Or run the `sherpa` command line yourself.], fill: soft)
  )
  down-arrow(label: [onboarding])
  card([Your private folder (me/)],
    [profile · achievement bullets, each with its source · interview stories · local SQLite database · drafts], fill: soft)
  down-arrow()
  grid(columns: (1fr, 26pt, 1fr, 26pt, 1fr), row-gutter: 8pt,
    step(1, [Find jobs], [public company job boards: Greenhouse, Lever, Ashby, SmartRecruiters, Adzuna]),
    right-arrow,
    step(2, [Score the fit], [from the full job description; a requirement you don't meet caps the score]),
    right-arrow,
    step(3, [Tailor resume + letter], [built only from your bullets; an invented number blocks the PDF]),
    [], [], [], [], down-arrow(),
    step(6, [Prepare for interviews], [your stories and screening answers, matched to the job]),
    left-arrow,
    step(5, [Track and follow up], [applied, screen, interview, offer or rejection; nudges when it goes quiet]),
    left-arrow,
    step(4, [You apply], [Job Sherpa never submits anything for you]),
  )
})
