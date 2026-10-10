#!/usr/bin/env python3
"""Regenerate the SEO / LLM artefacts of the site from index.html + script.js.

Run from the repository root after any content change:

    python3 tools/build_seo.py

It rewrites, idempotently:
  - the meta tags, hreflang links, JSON-LD and FAQ block of index.html (FR)
  - en/index.html, a static English version (same markup, strings from script.js)
  - sitemap.xml, llms.txt
The translation strings stay in script.js (single source of truth).
"""
import datetime
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://www.garance-provence.com"
OG_IMAGE = f"{SITE}/images/og-garance.jpg"
PHONE_E164, PHONE_DISPLAY = "+33607560623", "06 07 56 06 23"
EMAIL = "contact@garance-provence.com"

META = {
    "fr": {
        "title": "La Garance en Provence — Location de vacances au Thor",
        "description": "Ancien Relais de Poste du XVIIe siècle restauré au Thor, entre Avignon et le Luberon. 6 chambres, 12 personnes, piscine. Location exclusive à la semaine.",
        "og_title": "La Garance en Provence — Location de vacances en Provence",
        "og_description": "Ancien Relais de Poste du XVIIe siècle, 6 chambres, piscine à débordement, entre Avignon et le Luberon.",
        "ld_description": "Ancien Relais de Poste du XVIIe siècle restauré. 6 chambres avec salle de douche privative, piscine à débordement de 17 m, entre Avignon et le Luberon.",
        "price_range": "6800€ - 8000€ / semaine",
        "locale": "fr_FR",
        "url": f"{SITE}/",
    },
    "en": {
        "title": "La Garance en Provence — Holiday rental in Le Thor, Provence",
        "description": "Restored 17th-century coaching inn in Le Thor, between Avignon and the Luberon. 6 bedrooms, 12 guests, pool. Exclusive weekly rental.",
        "og_title": "La Garance en Provence — Holiday rental in Provence",
        "og_description": "17th-century former coaching inn, 6 bedrooms, infinity pool, between Avignon and the Luberon.",
        "ld_description": "Restored 17th-century former coaching inn. 6 bedrooms with private shower rooms, 17 m infinity pool, between Avignon and the Luberon.",
        "price_range": "€6,800 - €8,000 / week",
        "locale": "en_US",
        "url": f"{SITE}/en/",
    },
}


# ---------------------------------------------------------------- strings
def load_strings():
    src = (ROOT / "script.js").read_text()
    out, cur = {"fr": {}, "en": {}}, None
    entry = re.compile(r"^\s{6}([a-z0-9_]+):\s*'((?:[^'\\]|\\.)*)',?\s*$")
    for line in src.splitlines():
        m = re.match(r"^\s{4}(fr|en): \{\s*$", line)
        if m:
            cur = m.group(1)
            continue
        if cur:
            e = entry.match(line)
            if e:
                v = e.group(2).replace("\\'", "'").replace("\\\\", "\\")
                v = re.sub(r"\\u([0-9a-fA-F]{4})", lambda x: chr(int(x.group(1), 16)), v)
                out[cur][e.group(1)] = v
    assert len(out["fr"]) > 100 and set(out["fr"]) == set(out["en"]), "script.js dictionaries out of sync"
    return out


T = load_strings()


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


# ---------------------------------------------------------------- JSON-LD
def jsonld_blocks(lang):
    t, meta = T[lang], META[lang]
    rooms = []
    for i in range(1, 7):
        parts = [t.get(f"room{i}_tag1"), t.get(f"room{i}_tag2"), t.get(f"room{i}_desc")]
        rooms.append({
            "@type": "HotelRoom",
            "name": t[f"room{i}_title"],
            "description": " ".join(p.rstrip(".") + "." for p in parts if p),
        })
    business = {
        "@context": "https://schema.org",
        "@type": "LodgingBusiness",
        "name": "La Garance en Provence",
        "description": meta["ld_description"],
        "url": meta["url"],
        "image": OG_IMAGE,
        "inLanguage": lang,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "4010 Route de Saint Saturnin d'Avignon",
            "addressLocality": "Le Thor",
            "postalCode": "84250",
            "addressRegion": "Vaucluse",
            "addressCountry": "FR",
        },
        "geo": {"@type": "GeoCoordinates", "latitude": 43.905, "longitude": 4.978},
        "telephone": PHONE_E164,
        "email": EMAIL,
        "starRating": {"@type": "Rating", "ratingValue": "3"},
        "numberOfRooms": 6,
        "maximumAttendeeCapacity": 12,
        "amenityFeature": [
            {"@type": "LocationFeatureSpecification", "name": t[f"amen{i}_title"], "value": True}
            for i in range(1, 11)
        ],
        "containsPlace": rooms,
        "checkinTime": "16:00",
        "checkoutTime": "10:00",
        "priceRange": meta["price_range"],
        "currenciesAccepted": "EUR",
    }
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "inLanguage": lang,
        "mainEntity": [
            {"@type": "Question", "name": t[f"faq_q{i}"],
             "acceptedAnswer": {"@type": "Answer", "text": t[f"faq_a{i}"]}}
            for i in range(1, 9)
        ],
    }
    dump = lambda d: json.dumps(d, ensure_ascii=False, indent=2)
    return (
        '  <script type="application/ld+json">\n' + dump(business) + "\n  </script>\n"
        '  <script type="application/ld+json">\n' + dump(faq) + "\n  </script>"
    )


# ---------------------------------------------------------------- FAQ html
def faq_html():
    t = T["fr"]
    items = "\n".join(
        f'        <details class="faq-item reveal">\n'
        f'          <summary data-i18n="faq_q{i}">{html.escape(t[f"faq_q{i}"], quote=False)}</summary>\n'
        f'          <p data-i18n="faq_a{i}">{html.escape(t[f"faq_a{i}"], quote=False)}</p>\n'
        f"        </details>"
        for i in range(1, 9)
    )
    return (
        '  <section id="faq" class="faq">\n'
        '    <div class="container">\n'
        f'      <h2 class="section-title reveal" data-i18n="faq_title">{t["faq_title"]}</h2>\n'
        '      <hr class="section-divider">\n'
        '      <div class="faq-list">\n' + items + "\n      </div>\n"
        "    </div>\n"
        "  </section>"
    )


# ---------------------------------------------------------------- head
def set_meta(doc, lang):
    m = META[lang]
    other = "en" if lang == "fr" else "fr"
    def rep(pattern, repl, flags=0):
        nonlocal doc
        new, n = re.subn(pattern, lambda _m: repl, doc, count=1, flags=flags)
        assert n == 1, pattern
        doc = new
    q = lambda s: html.escape(s, quote=True)
    rep(r"<title>.*?</title>", f"<title>{q(m['title'])}</title>", re.S)
    rep(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{q(m["description"])}">')
    rep(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{m["url"]}">')
    rep(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{q(m["og_title"])}">')
    rep(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{q(m["og_description"])}">')
    rep(r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{m["url"]}">')
    rep(r'<meta property="og:image" content="[^"]*">', f'<meta property="og:image" content="{OG_IMAGE}">')
    doc = re.sub(r'\n  <meta property="og:locale:alternate"[^>]*>', "", doc)
    rep(r'<meta property="og:locale" content="[^"]*">',
        f'<meta property="og:locale" content="{m["locale"]}">\n'
        f'  <meta property="og:locale:alternate" content="{META[other]["locale"]}">')
    rep(r'<meta name="twitter:title" content="[^"]*">', f'<meta name="twitter:title" content="{q(m["og_title"])}">')
    rep(r'<meta name="twitter:description" content="[^"]*">', f'<meta name="twitter:description" content="{q(m["og_description"])}">')
    rep(r'<meta name="twitter:image" content="[^"]*">', f'<meta name="twitter:image" content="{OG_IMAGE}">')
    # hreflang alternates (idempotent)
    doc = re.sub(r'\n  <link rel="alternate" hreflang="[^"]*" href="[^"]*">', "", doc)
    alt = (
        f'\n  <link rel="alternate" hreflang="fr" href="{META["fr"]["url"]}">'
        f'\n  <link rel="alternate" hreflang="en" href="{META["en"]["url"]}">'
        f'\n  <link rel="alternate" hreflang="x-default" href="{META["fr"]["url"]}">'
    )
    doc = re.sub(r'(<link rel="canonical" href="[^"]*">)', lambda x: x.group(1) + alt, doc, count=1)
    return doc


def inject_jsonld(doc, lang):
    block = ("<!-- seo:jsonld:start (généré par tools/build_seo.py) -->\n" + jsonld_blocks(lang) +
             "\n  <!-- seo:jsonld:end -->")
    if "<!-- seo:jsonld:start" in doc:
        return re.sub(r"<!-- seo:jsonld:start.*?<!-- seo:jsonld:end -->", lambda _: block, doc, flags=re.S)
    new, n = re.subn(r'<script type="application/ld\+json">.*?</script>', lambda _: block, doc, count=1, flags=re.S)
    assert n == 1
    return new


def inject_faq(doc):
    block = "<!-- seo:faq:start (généré par tools/build_seo.py) -->\n" + faq_html() + "\n  <!-- seo:faq:end -->"
    if "<!-- seo:faq:start" in doc:
        return re.sub(r"<!-- seo:faq:start.*?<!-- seo:faq:end -->", lambda _: block, doc, flags=re.S)
    marker = "  <!-- ============== LOCATION ============== -->"
    assert marker in doc
    return doc.replace(marker, "  " + block + "\n\n" + marker, 1)


# ---------------------------------------------------------------- english page
EN_KEYWORDS = "holiday rental provence, le thor, vaucluse, luberon, avignon, swimming pool, character house, exclusive rental"

def to_english(fr_doc):
    doc = set_meta(fr_doc, "en")
    doc = inject_jsonld(doc, "en")
    doc = doc.replace('<html lang="fr">', '<html lang="en">', 1)
    doc = re.sub(r'<meta name="keywords" content="[^"]*">', f'<meta name="keywords" content="{EN_KEYWORDS}">', doc, count=1)
    t = T["en"]

    def sub_text(m):
        tag, before, key, after, inner = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if tag in ("input", "textarea") or key not in t:
            return m.group(0)
        return f"<{tag}{before}data-i18n=\"{key}\"{after}>{t[key]}</{tag}>"

    doc = re.sub(r'<(\w+)\b([^>]*?)data-i18n="([^"]+)"([^>]*)>(.*?)</\1>', sub_text, doc, flags=re.S)

    def sub_placeholder(m):
        key = m.group(2)
        tag = m.group(0)
        if key in t:
            return re.sub(r'placeholder="[^"]*"', f'placeholder="{html.escape(t[key], quote=True)}"', tag)
        return tag
    doc = re.sub(r'<(input|textarea)\b[^>]*data-i18n="([^"]+)"[^>]*>', sub_placeholder, doc)

    # make relative URLs root-relative (the page lives in /en/)
    def root_rel(m):
        attr, val = m.group(1), m.group(2)
        if re.match(r"(https?:|//|#|/|mailto:|tel:|data:|javascript:)", val):
            return m.group(0)
        return f'{attr}="/{val}"'
    doc = re.sub(r'\b(href|src)="([^"]*)"', root_rel, doc)
    doc = re.sub(r"url\('(?!/|https?:|data:)([^']+)'\)", r"url('/\1')", doc)
    return doc


# ---------------------------------------------------------------- sitemap / llms
def sitemap(today):
    def url(loc, prio, freq, alts=()):
        links = "".join(
            f'\n    <xhtml:link rel="alternate" hreflang="{h}" href="{u}"/>' for h, u in alts)
        return (f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today}</lastmod>\n"
                f"    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>{links}\n  </url>")
    alts = [("fr", META["fr"]["url"]), ("en", META["en"]["url"]), ("x-default", META["fr"]["url"])]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + url(META["fr"]["url"], "1.0", "monthly", alts) + "\n"
        + url(META["en"]["url"], "0.9", "monthly", alts) + "\n"
        + url(f"{SITE}/booking.html", "0.8", "weekly") + "\n</urlset>\n"
    )


def llms_txt(today):
    f = T["fr"]
    rooms = "\n".join(
        f"- {f[f'room{i}_title']} : " + ", ".join(
            x.rstrip(".") for x in (f.get(f"room{i}_tag1"), f.get(f"room{i}_tag2"), f.get(f"room{i}_desc")) if x) + "."
        for i in range(1, 7))
    amen = "\n".join(f"- {f[f'amen{i}_title']} : {f[f'amen{i}_desc']}" for i in range(1, 11))
    faq = "\n\n".join(f"### {f[f'faq_q{i}']}\n{f[f'faq_a{i}']}" for i in range(1, 9))
    return f"""# La Garance en Provence

> Location de vacances exclusive au Thor (Vaucluse, Provence) : ancien Relais de Poste du XVIIe siècle restauré, 6 chambres, 12 personnes, piscine à débordement de 17 m, entre Avignon et le Luberon. Meublé de tourisme classé 3 étoiles. Location à la semaine de l'ensemble de la propriété. / Exclusive holiday rental in Le Thor (Vaucluse, Provence): restored 17th-century coaching inn, 6 bedrooms, 12 guests, 17 m infinity pool, between Avignon and the Luberon. Weekly rental of the whole property.

Dernière mise à jour / last updated: {today}

## Pages
- [Accueil (français)]({META['fr']['url']}) : présentation, chambres, équipements, galerie, tarifs, FAQ, contact
- [Home (English)]({META['en']['url']}) : same content in English
- [Réserver / Booking]({SITE}/booking.html) : calendrier des disponibilités et demande de réservation

## Faits clés
- Adresse : 4010 Route de Saint Saturnin d'Avignon, 84250 Le Thor, Vaucluse, France
- Capacité : 12 personnes, 6 chambres, chacune avec salle de douche privative à l'italienne
- Location exclusive de la propriété, à la semaine
- Arrivée à partir de 16 h, départ avant 10 h
- Propriétaires : Régis et Chantal Sanglier
- Téléphone : {PHONE_DISPLAY} ({PHONE_E164})
- Email : {EMAIL}
- Langues du site : français, anglais

## Les six chambres
{rooms}

## Équipements
{amen}

## Questions fréquentes
{faq}
"""


# ---------------------------------------------------------------- main
def main():
    today = datetime.date.today().isoformat()
    if len(sys.argv) > 1:
        today = sys.argv[1]
    index = (ROOT / "index.html").read_text()
    index = set_meta(index, "fr")
    index = inject_jsonld(index, "fr")
    index = inject_faq(index)
    (ROOT / "index.html").write_text(index)

    (ROOT / "en").mkdir(exist_ok=True)
    (ROOT / "en" / "index.html").write_text(to_english(index))
    (ROOT / "sitemap.xml").write_text(sitemap(today))
    (ROOT / "llms.txt").write_text(llms_txt(today))
    print("ok: index.html, en/index.html, sitemap.xml, llms.txt")


if __name__ == "__main__":
    main()
