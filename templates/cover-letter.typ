// Cover letter template. Same header and type as the resume (theme.typ), with
// wider margins: letters read better with more white space.
#import "theme.typ": base, header, colors, rule

#let data = json(bytes(sys.inputs.data))
#let body-size = 10.6pt

#set document(title: data.contact.name + " - Cover Letter", author: data.contact.name)
#set page(paper: data.at("paper", default: "a4"),
          margin: (top: 46pt, bottom: 46pt, left: 54pt, right: 54pt))
#show: base
#set text(size: body-size)
#set par(leading: 0.62em, spacing: 1.15em)

#header(data.contact, gap-after: 8pt)
#rule()
#v(12pt)
#text(size: body-size - 0.3pt, fill: colors.meta, data.date)
#v(8pt)

#data.at("greeting", default: "Dear Hiring Team,")

#for p in data.paragraphs [
  #p

]
#data.at("sign_off", default: "Thank you for your time and consideration. I look forward to the opportunity to discuss how I can contribute to your team.")

#data.at("closing", default: "Sincerely,") \
#text(weight: 600, data.contact.name)
