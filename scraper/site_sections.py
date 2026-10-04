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
    # Promotions on the Marketplace (and the brand-page "has a live promotion" callouts that link to it): 10 entries,
    # not yet representative. The Marketplace page itself (the stockists) stays live, linked from the footer.
    "promotions": "10 entries; not yet representative",
}


def is_hidden(name):
    return name in HIDDEN_SECTIONS
