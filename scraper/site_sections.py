"""Which sections of the site are hidden for now (2026-10-04). One switch per section: a hidden section's
page is not generated (and any old file is removed), its links leave the footers and the sitemap, and
nothing else points at it. The data, the generator and the code stay, so bringing a section back is
removing its name here and regenerating.

Why these are hidden: the planned traffic test sends buyers of independent design to the site, and a
section that is thin, narrow or not yet representative only gives them something to parse that does not
help (and can undercut trust). Add a name, with the reason, to hide another.
"""

HIDDEN_SECTIONS = {
    # The Craftspeople chip and panel on For Creators: 20 firms, thin, and not needed for the test.
    "craftspeople": "thin (20 firms); not needed for the traffic test",
    # /marketplace.html (retailers and Promotions): 135 retailers, ~90% in five Nordic countries and
    # dominated by two brands (Orsjo 69, HAY 63); Promotions is 10 entries. Not yet representative.
    "marketplace": "narrow (Nordic, two brands dominate) and not yet representative; Promotions is 10 entries",
}


def is_hidden(name):
    return name in HIDDEN_SECTIONS
