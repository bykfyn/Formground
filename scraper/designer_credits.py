"""Turns a product's raw designer credit into the individual designers it names (2026-10-04).

Makers' sites credit designers however they like: "Marcello Jori, Massimo Giacon", "LPWK , Marcello Jori" (stray
space), "Ben van Berkel / UNStudio", "French designer brothers Ronan and Erwan Bouroullec", and the catch-all
"Aa.Vv." (Italian "autori vari": various authors, not a person). Left alone, each variant became its own designer
page - duplicates, joined names, a page for a non-designer - and four titles ran past 70 characters.

split_credit(raw) returns the designers to credit, so a piece shows on every named designer's page:
  - whitespace is normalised ("LPWK , X" == "LPWK, X");
  - catch-all credits return [] (the piece simply has no designer page credit);
  - a few hand-checked credits are spelled out in OVERRIDES;
  - otherwise a comma or " / " separates designers.
Studio duos written with "&" ("Anderssen & Voll", "Tham & Videgard") are one name and stay whole.
The database keeps the raw credit; only the designer pages and their sitemap counts use this.
"""
import re

CATCH_ALL = {"aa.vv.", "aa. vv.", "aavv", "various", "various authors", "autori vari", "unknown"}

OVERRIDES = {
    "arne jacobsen & flemming lassen, arne jacobsen": ["Arne Jacobsen", "Flemming Lassen"],
    "french designer brothers ronan and erwan bouroullec": ["Ronan Bouroullec", "Erwan Bouroullec"],
    "ronan & erwan bouroullec": ["Ronan Bouroullec", "Erwan Bouroullec"],
    "luigi caccia dominioni, livio e pier giacomo castiglioni":
        ["Luigi Caccia Dominioni", "Livio Castiglioni", "Pier Giacomo Castiglioni"],
    "vittorio, lodovico and giotto gregotti, meneghetti and stoppino":
        ["Vittorio Gregotti", "Lodovico Meneghetti", "Giotto Stoppino"],
    "franco and franca albini and helg": ["Franco Albini", "Franca Helg"],
    "stockholm-based taf studio": ["TAF Studio"],
}


def _clean(raw):
    return re.sub(r"\s+,", ",", " ".join((raw or "").split()))


def split_credit(raw):
    name = _clean(raw)
    key = name.lower()
    if not name or key in CATCH_ALL:
        return []
    if key in OVERRIDES:
        return list(OVERRIDES[key])
    parts = [p.strip() for p in re.split(r",| / ", name)]
    seen, out = set(), []
    for p in parts:
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def credited_counts(rows):
    """{designer: number of products} from (raw_credit, product_count) pairs, after splitting."""
    counts = {}
    for raw, n in rows:
        for name in split_credit(raw):
            counts[name] = counts.get(name, 0) + n
    return counts
