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


# --- wave 1 (approved 2026-10-06) ---
EL_KRETSEN = ("Recycling electronics and light sources in Sweden", "https://www.el-kretsen.se/")
COLOR_TEMP = ("How light colour temperature is measured", "https://en.wikipedia.org/wiki/Color_temperature")
LUMEN = ("How lumens measure brightness", "https://en.wikipedia.org/wiki/Lumen_(unit)")
EPREL = ("EU energy label database for light sources and lamps", "https://eprel.ec.europa.eu/screen/home")

GUIDES += [
    {
        "slug": "portable-lamps",
        "group": "Lighting",
        "noun": "portable lamps",
        "title": "Portable lamps",
        "edit_slug": "portable-lamps",
        "summary": "Battery and run time, charging, safe use, light and weather for lamps you can move around.",
        "about": (
            "A portable lamp runs on a rechargeable battery, so it can sit on a dinner table one evening and out on "
            "the terrace the next. Without a cable it is freer to place, but it brings questions a plugged-in lamp does "
            "not: how long it runs, how it charges, how long the battery lasts and what happens to it afterwards."
        ),
        "teasers": [
            "Run time depends on brightness: ask for the hours at the level you will actually use.",
            "Check how it charges (cable, dock or mat) and whether the battery can be replaced.",
            "If it goes outdoors, look for an IP rating, which describes protection against dust and water.",
        ],
        "intro": (
            "A portable lamp trades the cable for a battery, and that changes what is worth checking. The numbers "
            "are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Battery and run time", [
                "Run time depends on brightness: a lamp that lasts many hours on its lowest setting may last far fewer at full brightness. Ask for the run time at the level you would really use.",
                "Battery size is given in mAh or Wh. Compare like with like, and treat the maker's run time as the better guide.",
            ]),
            ("Charging", [
                "Check how it charges: a cable (often USB-C), a dock or a mat, and how long a full charge takes.",
                "Some lamps can be used while charging and some cannot. If you want to leave it on a table all evening, this matters.",
                "A standard USB-C connection means you may be able to use a charger you already own; check the power it needs.",
            ]),
            ("Battery life and replacement", [
                "Rechargeable batteries lose capacity over the years, so a lamp that lasts all evening when new may not in a few years. Check whether the battery can be replaced, by you or by the maker, and whether replacements are sold.",
            ]),
            ("Safe use", [
                "Use the charger and cable the maker specifies, keep the lamp away from heat, and follow the charging instructions on leaving it unattended.",
                "A battery that is damaged, swollen or very hot should be taken out of use.",
            ]),
            ("Light", [
                "Brightness is given in lumens. Warm white (around 2700 K) is the usual choice at a table; cooler light suits work.",
                "Check how it dims: set steps, a dial or a touch dimmer.",
            ]),
            ("Outdoors and water", [
                "Look for an IP rating. A lamp that is splash-resistant is not necessarily meant to be left out in the rain or put in water.",
            ]),
            ("Weight and stability", [
                "A handle helps if you will carry it. A light, narrow lamp can tip in a breeze or on an uneven surface.",
            ]),
            ("When it is time to dispose of it", [
                "Batteries and electronic products should not go in household waste. Take them to a recycling point.",
            ]),
            ("Questions worth asking the maker", [
                "How many hours at the brightness I will use? How long to charge? Can I use it while it charges? Is the battery replaceable, and is a replacement sold? What is the IP rating? What is the warranty on the battery?",
            ]),
        ],
        "sources": [
            ("How IP ratings work (protection against dust and water)", "https://en.wikipedia.org/wiki/IP_Code"),
            ("Lithium-ion batteries explained", "https://en.wikipedia.org/wiki/Lithium-ion_battery"),
            ("USB-C, the common charging connector", "https://en.wikipedia.org/wiki/USB-C"),
            ("EU rules on batteries", "https://environment.ec.europa.eu/topics/waste-and-recycling/batteries_en"),
            ("EU rules on recycling electrical and electronic equipment", "https://environment.ec.europa.eu/topics/waste-and-recycling/waste-electrical-and-electronic-equipment-weee_en"),
            EL_KRETSEN,
            ("Advice to households, including fire and battery safety, from the Swedish Civil Defence Agency (in Swedish)", "https://www.mcf.se/sv/rad-till-privatpersoner/"),
            GREEN_CLAIMS,
        ],
    },
    {
        "slug": "table-lamps",
        "group": "Lighting",
        "noun": "table lamps",
        "title": "Table lamps",
        "edit_slug": "table-lamps",
        "summary": "Scale and height, light and shade, switch and cable, materials and care for lamps that stand on a surface.",
        "about": (
            "A table lamp lights a corner, a bedside or a desk, and it also furnishes the surface it sits on. The "
            "base, the shade and the height decide where the light falls and how the lamp looks in the room. Some "
            "give a soft glow across a room; others throw a tight beam for reading."
        ),
        "teasers": [
            "Check where the shade's lower edge falls against your eyes when you are seated or in bed, to avoid glare.",
            "Check the bulb fitting, the maximum wattage and whether it can be dimmed.",
            "Look at where the switch is and how long the cable is before you buy.",
        ],
        "intro": (
            "A table lamp lights a place and furnishes the surface it stands on. These are the things worth settling "
            "before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Scale and height", [
                "For reading, the light should fall on the page without shining in your eyes. A common rule of thumb is that the lower edge of the shade sits around eye level when you are seated.",
                "Beside a bed or sofa, check the lamp's height against the surface it stands on. A lamp that looks right on a tall console can loom over a low table.",
                "Leave room on the surface for the things that live there: a book, a glass, a phone.",
            ]),
            ("Light and shade", [
                "An opaque shade sends light up and down; a translucent one glows and spreads light more widely. A narrow shade gives a tighter pool for reading.",
                "Check the fitting (for example E27, E14 or a built-in LED), the maximum wattage, whether it can be dimmed, and whether a bulb is included.",
                "Warm white light (around 2700 K) is the usual choice for living rooms and bedrooms.",
            ]),
            ("Switch and cable", [
                "Check where the switch is (on the cable, at the base or on the shade) and whether you can reach it from where you sit.",
                "Check the cable length and the position of the nearest socket. A long cable can be a nuisance, a short one limits where the lamp can go.",
            ]),
            ("Materials and care", [
                "Fabric and paper shades collect dust and can fade in strong sun. Glass and metal wipe clean. Ceramic and stone bases are heavy, which helps stability but makes them harder to move.",
                "A lamp should be stable: check the base against the height, especially around children and pets.",
            ]),
            ("Safety and longevity", [
                "Check that the lamp carries the safety marking required where you live (such as CE in the EU).",
                "A lamp lasts longer if its parts can be replaced: the bulb or LED module, the switch, the cable.",
            ]),
            ("Questions worth asking the maker", [
                "Exact height and shade size? Which bulb fits, and is one included? Where is the switch and how long is the cable? Which plug does it come with? Can the shade and cable be replaced? What are the delivery and return terms?",
            ]),
        ],
        "sources": [COLOR_TEMP, LUMEN, EPREL, GREEN_CLAIMS],
    },
    {
        "slug": "floor-lamps",
        "group": "Lighting",
        "noun": "floor lamps",
        "title": "Floor lamps",
        "edit_slug": "floor-lamps",
        "summary": "Height and reach, stability, light direction and cables for lamps that stand on the floor.",
        "about": (
            "A floor lamp is the lamp that does not need a table. It can stand beside a sofa for reading, behind a "
            "chair for ambient light, or in a corner to lift a dark room. Heights run from low sculptural pieces to "
            "tall arcs that reach across a seating area."
        ),
        "teasers": [
            "Check where the light falls from where you will sit, not just how the lamp looks.",
            "A tall, slim lamp needs a stable base: check the footprint and weight.",
            "Check the cable length and where the nearest socket is, so the cable does not cross the floor.",
        ],
        "intro": (
            "A floor lamp lights a place without taking a table. These are the things worth settling before you "
            "choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Height and reach", [
                "For reading in a chair, the light should fall over your shoulder onto the page, with the shade or head near eye level when you are seated.",
                "Arc lamps reach out over a seat. Check the reach and the weight of the base so it can carry the arm without tipping.",
                "Floor lamps are commonly about 140-180 cm tall. A taller lamp suits a high-ceilinged room or a corner.",
            ]),
            ("Stability", [
                "A tall, slim lamp needs a wide or weighted base. Check the footprint, particularly around children, pets and busy walkways.",
            ]),
            ("Light", [
                "Uplight spreads light on the ceiling for a soft general glow; a downlight or adjustable head gives a focused beam for reading.",
                "Check the fitting, the maximum wattage, whether it can be dimmed, and whether a bulb is included. Warm white light (around 2700 K) is the usual choice for living rooms.",
            ]),
            ("Switch and cable", [
                "Check where the switch or dimmer is: on the stem, on the cable or at the foot.",
                "Plan where the cable will run. A cable across the floor is a trip hazard; the socket's position often decides where the lamp can go.",
            ]),
            ("Materials and care", [
                "Fabric and paper shades collect dust and can fade in sun. Metal finishes can chip; raw metals change with age.",
                "Check the weight if you will move it, and whether it comes apart for transport.",
            ]),
            ("Longevity and repair", [
                "A lamp lasts longer if its parts can be replaced: the bulb or LED module, the switch, the cable. Slim, tall lamps are easier to ship when they come apart.",
            ]),
            ("Questions worth asking the maker", [
                "Exact height, reach and base size? Where is the switch and how long is the cable? Which bulb fits, and is one included? Can it be dimmed? Are spare parts available? What are the delivery and return terms?",
            ]),
        ],
        "sources": [COLOR_TEMP, LUMEN, EPREL, GREEN_CLAIMS],
    },
    {
        "slug": "chairs",
        "group": "Furniture",
        "noun": "chairs",
        "title": "Chairs",
        "edit_slug": "chairs",
        "summary": "Use, size and fit, comfort, frame and materials for chairs of every kind.",
        "about": (
            "A chair is judged by sitting in it, which is the one thing a listing cannot offer. Some are made for a "
            "dining table and an hour at a time; others for a corner and a whole afternoon. What a chair is for, how "
            "long you will sit and what it sits at decide most of what matters."
        ),
        "teasers": [
            "Decide what it is for and how long you will sit: a dining chair and a lounge chair are different things.",
            "Check the seat height against your table or desk; a common gap is about 25-30 cm to the underside.",
            "Look at the frame and the joints, and whether covers and seat pads can be replaced.",
        ],
        "intro": (
            "A chair is judged by sitting in it, which a listing cannot offer. These are the things worth settling "
            "before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("What it is for", [
                "A dining chair is for upright sitting at a table; a lounge chair or armchair is for relaxing; a desk chair needs to adjust. Decide the use and how long you will sit before you look at style.",
            ]),
            ("Size and fit", [
                "Seat height is commonly about 43-47 cm. Check it against the table or desk: you want roughly 25-30 cm between the seat and the underside of the top.",
                "Allow about 50-60 cm of table edge for each chair. Chairs with arms need more room and may not slide under the table.",
                "Check the seat depth and width, and whether chairs stack, fold or fit the space when not in use.",
            ]),
            ("Comfort", [
                "Seat depth, back angle and the firmness of any padding matter more than looks. If you can, sit in one before buying, and check the return terms.",
                "Removable cushions and covers make a chair easier to keep fresh.",
            ]),
            ("Frame and materials", [
                "Solid wood frames can usually be repaired and refinished; check how the joints are made. Plywood and bent wood are light and strong in the right shapes. Metal is durable and usually coated: powder-coated metal can chip, raw metal changes with age.",
                "Plastic and moulded chairs are easy to clean and often suit outdoor use if made for it.",
                "For upholstered chairs, a fabric's abrasion rating (often given as a Martindale number) shows its resistance to wear: higher is more resistant. Leather patinates with use.",
                "A chair for outdoors must be made for weather. An indoor chair left outside usually is not suitable.",
            ]),
            ("Floors and use", [
                "Check the feet. Hard glides can scratch floors; felt or rubber glides help, and are often replaceable.",
                "Check the weight if you will move it often, and whether it wobbles on an uneven floor.",
            ]),
            ("Longevity and repair", [
                "Parts that can be replaced or tightened keep a chair going: glides, seat pads, covers and fixings. Woven or upholstered seats can often be redone.",
            ]),
            ("Questions worth asking the maker", [
                "Exact seat height, width and depth? What are the frame and the seat made of? Are covers, pads and glides replaceable? Is it stackable? What are the delivery and return terms?",
            ]),
        ],
        "sources": [
            FSC,
            ("PEFC, another forest certification scheme", "https://pefc.org/"),
            ("OEKO-TEX Standard 100 (textiles tested for harmful substances)", "https://www.oeko-tex.com/en/our-standards/oeko-tex-standard-100"),
            ("Global Organic Textile Standard (organic fibres)", "https://global-standards.org/"),
            SWAN,
            GREEN_CLAIMS,
        ],
    },
]


# --- seasonal (approved 2026-10-06) ---
GUIDES += [
    {
        "slug": "candle-holders",
        "group": "Objects",
        "noun": "candle holders",
        "title": "Candle holders",
        "edit_slug": "candle-holders",
        "summary": "Fit, stability, heat and safe use for the holders that give a flame somewhere to stand.",
        "about": (
            "A candle holder gives a flame somewhere safe and steady to stand, and it is often the part of the "
            "arrangement that stays on the table long after the candle has gone. They range from single tapers and "
            "pillar holders to tealight cups, candelabras and wall-mounted sconces, in glass, ceramic, metal, wood "
            "and stone."
        ),
        "teasers": [
            "Check the holder suits the candle: taper, pillar and tealight holders are different things, and taper sizes vary.",
            "Check the base is wide or weighted enough to stay upright; taller holders tip more easily.",
            "Use on a level, heat-resistant surface, away from anything that burns, and never leave a candle burning unattended.",
        ],
        "intro": (
            "A candle holder keeps a flame upright and steady, and then stays on the table when the candle is gone. "
            "These are the things worth settling before you choose one. The numbers are common rules of thumb, not "
            "fixed rules."
        ),
        "sections": [
            ("Fit to the candle", [
                "Taper, pillar, tealight and votive candles need different holders. Decide which you will burn before you choose.",
                "Taper candles vary in thickness between makers and countries, commonly around 2.0-2.4 cm. A candle that is too thin wobbles and one that is too thick will not fit, so check the socket's diameter against your candles.",
                "A holder designed for several candles (a candelabra, a row or a set) changes the whole table, so check the total height and spread.",
            ]),
            ("Stability", [
                "A wide or weighted base keeps a holder upright; tall, slim holders tip more easily. Take extra care around children, pets and busy tables.",
                "A holder for a hanging or wall position needs fixings suited to the wall and the weight.",
            ]),
            ("Heat and surfaces", [
                "Use a candle on a level, heat-resistant surface. Wood, fabric, paper and plastic nearby can catch fire.",
                "Thin glass can crack when heated unevenly; use glass that is made to hold a candle.",
                "Wooden holders should have a metal, glass or ceramic cup or insert where the flame sits.",
            ]),
            ("Safe use", [
                "Never leave a burning candle unattended, and put it out before you leave the room or go to sleep.",
                "Keep candles well clear of curtains, decorations and anything that can burn, and out of draughts.",
                "Trim the wick short before lighting.",
            ]),
            ("Materials and care", [
                "Metals such as brass and iron can darken or tarnish; coated metals can chip.",
                "Glass and ceramic wipe clean. To remove wax, let it harden (for example in a cool place) and lift it off rather than scraping hard; avoid pouring boiling water into glass.",
                "Wood and untreated stone can stain from wax.",
            ]),
            ("Outdoors and wind", [
                "For outdoors or a windy porch, look for a lantern or a holder with a windshield, and one made for weather.",
            ]),
            ("Questions worth asking the maker", [
                "Which candles does it take, and what is the socket's diameter? What is the base size and weight? Is the cup or insert replaceable? How should it be cleaned?",
            ]),
        ],
        "sources": [
            ("Safety with candles (NFPA)", "https://www.nfpa.org/education-and-research/home-fire-safety/candles"),
            ("Advice to households, including fire safety, from the Swedish Civil Defence Agency (in Swedish)", "https://www.mcf.se/sv/rad-till-privatpersoner/"),
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
