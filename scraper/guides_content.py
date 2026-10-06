"""
Buying-guide content and the facts line for type pages (MOCKUP, 2026-10-06; not live until approved).

What lives here: the hand-written text for each guide (general guidance only: no maker claims, no
sustainability labels, no ratings), plus the small helpers that turn a type's products into the preamble
and "about" facts. The generators (generate_guides_pages.py, generate_browse_pages.py) only render.

Figures in the guides are common rules of thumb; have a design professional check them and decide on a
reviewer name / "last reviewed" date before this goes live. Source links are explainers, not endorsements,
and were checked to load on 2026-10-06 - re-check them on a schedule, sites move pages.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

LABEL_NOTE = (
    "A label covers one aspect of a product, such as where the wood came from or which chemicals are in a "
    "textile, not its whole footprint. These pages explain what each covers; they are not endorsements, and "
    "Formground does not rate products."
)

GREEN_CLAIMS = ("How to read environmental claims (EU)",
                "https://environment.ec.europa.eu/topics/circular-economy-topics/green-claims_en")
FSC = ("What FSC labels mean (forest management and chain of custody)", "https://fsc.org/en/label")
SWAN = ("The Nordic Swan Ecolabel (Sweden)", "https://www.svanen.se/")

GUIDES = [
    {
        "slug": "pendant-lamps",
        "group": "Lighting",
        "noun": "pendant lamps",
        "title": "Pendant lamps",
        "edit_slug": "pendant-lamps",
        "summary": "Height, light, installation, materials and care for lamps that hang from the ceiling.",
        "about": (
            "A pendant lamp hangs from the ceiling on a cable, chain or rod, and it does two jobs at once: it "
            "lights a place and it marks that place out in the room. Over a dining table, a kitchen island or a "
            "bedside it works as a focal point; over a stairwell or hallway it works as a landmark. Pendants "
            "range from a single shade on a long drop to clusters, rows and linear fittings, and from bare "
            "bulbs to deep opaque domes."
        ),
        "teasers": [
            "Over a table, the lower edge is commonly hung about 75-85 cm above the surface.",
            "Check the fitting, the maximum wattage and whether it can be dimmed.",
            "Fixed wiring should be done by a qualified electrician; rules differ by country.",
        ],
        "intro": (
            "A pendant lamp lights a place, marks it out, and hangs in the middle of your eyeline. These are "
            "the things worth settling before you choose one. The numbers are common rules of thumb, not "
            "fixed rules."
        ),
        "sections": [
            ("Height and size", [
                "Over a dining table or kitchen island, the lower edge is commonly hung about 75-85 cm above the surface, so nobody has to look around it. Hang lower in a low room and higher in a tall one.",
                "Over a walkway or stairs, keep the lower edge well clear of heads, at least about 2 metres above the floor.",
                "Over a table, choose a lamp (or a group) clearly narrower than the table, so it does not crowd the edges.",
                "If you want several pendants in a row, decide the number and spacing first: it changes the cost and the fixing.",
            ]),
            ("Light", [
                "Check the fitting (for example E27, E14 or a built-in LED), the maximum wattage, whether it can be dimmed, and whether a bulb is included.",
                "Warm white light (around 2700 K) is the usual choice for dining and living spaces.",
                "An opaque shade sends light down and leaves the ceiling dark. Glass, paper or fabric spreads it more widely. A bare bulb at eye level can glare, so think about how visible the light source is when you are seated.",
            ]),
            ("Installation", [
                "A hanging lamp needs a ceiling outlet where you want it. Fixed wiring should be done by a qualified electrician, and the rules differ by country.",
                "Heavy glass, stone or ceramic shades need fixings that suit your ceiling (concrete, joists or plasterboard).",
                "Check the cable or rod length and whether it can be shortened or adjusted. Plug-in versions need a visible cable to a socket.",
            ]),
            ("Materials and care", [
                "Metal: raw brass and untreated metals darken with age; painted or powder-coated finishes keep their look but can chip.",
                "Glass shows fingerprints and dust. Paper and fabric suit dry rooms and are less suited to kitchens, damp rooms or hot bulbs.",
                "Bathrooms and outdoor spaces need a fitting rated for damp or wet conditions (look for an IP rating).",
            ]),
            ("Longevity and repair", [
                "A lamp lasts longer if its parts can be replaced: the bulb or LED module, the cable, the socket, the ceiling plate. With a built-in LED, the whole lamp is effectively the part that wears out.",
                "A shade that can be cleaned or taken apart is easier to keep looking good.",
            ]),
            ("Questions worth asking the maker", [
                "What are the exact dimensions and drop? Is the bulb included and replaceable? Can the cable be shortened? Are spare parts and finishes available later? What are the delivery and return terms?",
            ]),
        ],
        "sources": [
            ("How IP ratings work (protection against dust and water)", "https://en.wikipedia.org/wiki/IP_Code"),
            ("EU energy label database for light sources and lamps", "https://eprel.ec.europa.eu/screen/home"),
            ("Electrical safety rules in Sweden, including who may do fixed installation work", "https://www.elsakerhetsverket.se/"),
            GREEN_CLAIMS,
        ],
    },
    {
        "slug": "dining-tables",
        "group": "Furniture",
        "noun": "dining tables",
        "title": "Dining tables",
        "edit_slug": "round-dining-tables",
        "summary": "Size and seating, space in the room, shape, materials and finish for the table a room is arranged around.",
        "about": (
            "A dining table is the piece a room is arranged around, so its size, shape and base matter as much "
            "as its look. Tops are round, oval, rectangular or square; bases are four legs, trestles, a single "
            "pedestal or a sled; and many extend with leaves to seat more people."
        ),
        "teasers": [
            "A common rule of thumb is about 60 cm of table edge per person, 70 cm to sit comfortably.",
            "Leave about 90-100 cm between the table edge and walls so chairs can be pulled out.",
            "Solid wood can usually be refinished; stone and ceramic are heavy and can chip at the edges.",
        ],
        "intro": (
            "A dining table is the piece a room is arranged around. These are the things worth settling before "
            "you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Size and seating", [
                "A common rule of thumb is about 60 cm of table edge per person, and 70 cm if you want to sit comfortably. A table of roughly 140-160 cm seats four to six; 180-200 cm seats six to eight.",
                "Round tables of about 100-120 cm seat four, and about 140-150 cm seat six.",
                "If the table extends, measure it both closed and open.",
            ]),
            ("Space in the room", [
                "Leave about 90-100 cm between the table edge and walls or furniture, so chairs can be pulled out and people can pass behind.",
            ]),
            ("Shape and base", [
                "Round and square tables suit square rooms and uneven numbers of guests. Rectangles suit long or narrow rooms.",
                "A pedestal or trestle base gives more freedom for knees and chairs than four corner legs. Check where the legs sit against your chair width.",
            ]),
            ("Height", [
                "Table height is commonly about 72-75 cm. Check it against your chairs: you want roughly 25-30 cm between the seat and the underside of the top.",
            ]),
            ("Materials and finish", [
                "Solid wood moves with the seasons and can usually be sanded and refinished. Veneer over a core is more stable but allows less refinishing.",
                "Oiled wood marks more easily but is easier to repair in one spot. Lacquered surfaces resist marks and are harder to repair.",
                "Stone and ceramic resist heat and scratches but are heavy and can chip at the edges. Glass shows every mark. Metal can dent or scratch.",
                "Whatever the material, protect the top from hot dishes and standing water.",
            ]),
            ("Practicalities", [
                "Check weight, and whether it will fit through your doors and stairwell. A table that comes apart is easier to move.",
                "Outdoor tables are made for weather. An indoor table left outside usually is not suitable.",
            ]),
            ("Longevity and repair", [
                "Look at how the legs attach, how the extension works, and where the leaves are stored. Parts that can be replaced or tightened keep a table going longer.",
            ]),
            ("Questions worth asking the maker", [
                "Exact dimensions and weight, how it ships, what finish is used and how to care for it, whether the finish can be redone, and the delivery and return terms.",
            ]),
        ],
        "sources": [
            FSC,
            ("PEFC, another forest certification scheme", "https://pefc.org/"),
            ("Cradle to Cradle Certified (product design for materials and reuse)", "https://c2ccertified.org/"),
            SWAN,
            GREEN_CLAIMS,
        ],
    },
    {
        "slug": "sofas",
        "group": "Furniture",
        "noun": "sofas",
        "title": "Sofas",
        "edit_slug": "two-seater-sofas",
        "summary": "Measuring, seat size, comfort, fabric and frame for the piece of seating you live with longest.",
        "about": (
            "A sofa is the largest piece of seating in most homes and the one you live with longest, so "
            "comfort, size and fabric matter more than a photo suggests. They range from compact two-seaters "
            "to modular systems that grow and rearrange, and from firm, upright frames to deep lounging seats."
        ),
        "teasers": [
            "Measure the route in (doors, stairwells, lifts) as well as the room.",
            "\"Two-seater\" differs between makers, so compare the width in centimetres.",
            "A higher fabric abrasion rating (often a Martindale number) means more resistance to wear.",
        ],
        "intro": (
            "A sofa is the piece of seating you live with longest. These are the things worth settling before "
            "you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Measure first", [
                "Measure the room, and the route in: doors, hallways, stairwells and lifts. A sofa that does not fit through the door is a common and costly surprise. Modular or flat-pack designs make this easier.",
                "Leave about 40-50 cm between the sofa and a coffee table, and room to walk around it.",
            ]),
            ("Size and seat", [
                "Labels such as \"two-seater\" differ between makers, so compare the width in centimetres.",
                "Seat height is commonly about 40-46 cm. A deeper seat (60 cm or more) suits lounging; a shallower one suits sitting upright and getting up easily.",
            ]),
            ("Comfort", [
                "Firmer or softer depends on the filling: foam, feathers, fibre or a mix. Feather-filled cushions need plumping; foam holds its shape.",
                "If you can, sit on one before buying, and check the return terms.",
            ]),
            ("Fabric and covers", [
                "A fabric's abrasion rating (often given as a Martindale number) shows its resistance to wear: higher means more resistant, and 15,000 or more is commonly cited for everyday family use.",
                "Natural fibres such as wool, linen and cotton breathe and age differently from synthetics. Leather patinates with use. Light colours show wear and stains sooner.",
                "Check whether covers are removable and how they can be cleaned.",
            ]),
            ("Frame and construction", [
                "Solid wood or plywood frames are generally more durable than particleboard. Ask how the frame is joined.",
            ]),
            ("Longevity and repair", [
                "Replaceable covers, cushion inserts and legs extend a sofa's life. Modular systems let you add, remove or replace one part.",
            ]),
            ("Questions worth asking the maker", [
                "Exact dimensions and weight, what the frame and filling are made of, whether fabric samples are available, and the delivery, assembly and return terms.",
            ]),
        ],
        "sources": [
            ("OEKO-TEX Standard 100 (textiles tested for harmful substances)", "https://www.oeko-tex.com/en/our-standards/oeko-tex-standard-100"),
            ("Global Organic Textile Standard (organic fibres)", "https://global-standards.org/"),
            ("What FSC labels mean, for wood frames", "https://fsc.org/en/label"),
            SWAN,
            GREEN_CLAIMS,
        ],
    },
]

GUIDES_BY_SLUG = {g["slug"]: g for g in GUIDES}
GROUP_ORDER = ["Furniture", "Lighting", "Objects"]


def _country_phrase(name):
    return f"the {name}" if name.startswith("United") else name


def type_facts(products):
    """Counts for the preamble and the about block, from the type's own products."""
    import query_engine as qe  # noqa: E402

    makers = {p["brand"] for p in products}
    countries = {}
    for p in products:
        c = qe.BRAND_COUNTRIES.get(p["brand"])
        if c:
            countries[c] = countries.get(c, 0) + 1
    cut = qe.new_cutoff_day()
    return {
        "total": len(products),
        "makers": len(makers),
        "countries": len(countries),
        "top_countries": sorted(countries.items(), key=lambda kv: -kv[1])[:4],
        "independent": len({b for b in makers if qe.BRAND_TIERS.get(b, "independent") == "independent"}),
        "new": sum(1 for p in products if qe.is_new_piece(p, cut)),
        "new_days": qe.NEW_ARRIVALS_WINDOW_DAYS if hasattr(qe, "NEW_ARRIVALS_WINDOW_DAYS") else 90,
    }


def preamble_text(guide, facts):
    return (f"{facts['total']:,} {guide['noun']} from {facts['makers']} makers in {facts['countries']} countries. "
            "Every piece links to the maker's own site.")


def facts_sentences(facts):
    """The data-derived second paragraph of the about block."""
    parts = []
    top = facts["top_countries"]
    if top:
        named = [f"{_country_phrase(n)} ({c} pieces)" if i == 0 else f"{_country_phrase(n)} ({c})"
                 for i, (n, c) in enumerate(top)]
        listing = ", ".join(named[:-1]) + " and " + named[-1] if len(named) > 1 else named[0]
        parts.append(f"Makers in {listing} lead the listing.")
    parts.append(f"{facts['independent']} of the {facts['makers']} makers are independent.")
    if facts["new"]:
        pieces = "piece is" if facts["new"] == 1 else "pieces are"
        parts.append(f"{facts['new']} {pieces} new from their makers in the last {facts['new_days']} days.")
    return " ".join(parts)
