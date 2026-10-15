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

OEKO_TEX = ("OEKO-TEX, which tests textiles for harmful substances", "https://www.oeko-tex.com/en/")
GOODWEAVE = ("GoodWeave, a certification aimed at ending child labour in rug weaving", "https://goodweave.org/")
KONSUMENTVERKET = ("Consumer rights and product safety from the Swedish Consumer Agency (in Swedish)", "https://www.konsumentverket.se/")
PEFC = ("PEFC, another forest certification scheme", "https://pefc.org/")

GUIDES += [
    {
        "slug": "armchairs",
        "group": "Furniture",
        "noun": "armchairs and lounge chairs",
        "title": "Armchairs and lounge chairs",
        "edit_slug": "armchairs",
        "summary": "Seat height and depth, support, upholstery, frame and care for the chair you sit in longest.",
        "about": (
            "An armchair or lounge chair is the seat people stay in: for reading, for talking, for an evening. "
            "Comfort depends on the shape of the seat and back more than on how soft it looks, and the same "
            "chair can suit one person and not another. They range from compact wooden chairs with a cushion to "
            "deep, low lounge chairs, swivel chairs and chairs with a matching footstool."
        ),
        "teasers": [
            "Seat height is commonly around 40-45 cm; a deep, low seat is harder to get out of.",
            "Check the depth of the seat against your legs, and whether the back supports your lower back or your head.",
            "Ask what the frame is made of, how the cushions are filled and whether the cover can be replaced.",
        ],
        "intro": (
            "An armchair is the piece of furniture you sit in longest, so how it fits you matters more than how it "
            "looks in a photograph. These are the things worth settling before you choose one. The numbers are "
            "common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Fit and posture", [
                "Seat height is commonly around 40-45 cm. A lower seat feels relaxed but is harder to get out of, which matters for older people and for anyone with stiff knees.",
                "Seat depth decides whether your back reaches the backrest while your knees still bend over the front edge. A deep seat suits tall people or sitting with the legs up; a shallower one suits upright sitting.",
                "A high back that supports the head suits long reading or resting; a lower back leaves the shoulders free and suits conversation.",
                "Arms should be at a height where your forearms rest without pushing the shoulders up, commonly around 20-25 cm above the seat.",
            ]),
            ("Seat and filling", [
                "Foam of a higher density holds its shape longer; feather and fibre fillings feel softer and need plumping. A combination is common.",
                "A firm seat feels less inviting in the shop and often more comfortable after an hour. If you can, ask how it feels when you have sat in it for a while.",
                "Loose cushions can be turned and refilled; fixed upholstery is smoother but harder to repair.",
            ]),
            ("Covers and fabric", [
                "Leather ages and can be treated; fabric varies widely. Wool and linen blends breathe, synthetic fibres resist stains, and light colours show marks sooner.",
                "Ask whether the cover can be taken off and washed, or replaced by the maker or an upholsterer.",
                "Check the fabric's rub rating (for example in Martindale cycles) if the chair will be used every day.",
            ]),
            ("Frame and construction", [
                "A solid wood frame with joints that are glued and screwed is common in chairs built to last; ask what the frame is made of and how it is joined.",
                "Swivel mechanisms and recliners are parts that wear; check whether they can be replaced.",
                "Legs set at an angle or with a metal base change how stable the chair is on a soft carpet or an uneven floor.",
            ]),
            ("Practicalities", [
                "Check the overall width against your door and your room; a chair that comes apart is easier to move.",
                "Leave space behind a chair that reclines or swivels, and check the weight if it will move often.",
                "Glides or felt pads protect the floor; ask which are included.",
            ]),
            ("Questions worth asking the maker", [
                "What are the seat height, depth and width? What is the frame made of? How is the seat filled and can it be refilled? Can the cover be replaced? What are the delivery and return terms?",
            ]),
        ],
        "sources": [FSC, PEFC, OEKO_TEX, SWAN, GREEN_CLAIMS],
    },
    {
        "slug": "coffee-tables",
        "group": "Furniture",
        "noun": "coffee tables",
        "title": "Coffee tables",
        "edit_slug": "coffee-tables",
        "summary": "Height, size and proportion, materials and edges for the low table in front of the sofa.",
        "about": (
            "A coffee table sits between the people and the things they put down: a cup, a book, a candle, a "
            "remote. It anchors a seating group and decides how easily you can move through it. They range from "
            "low round tables to long rectangular ones, nests of two or three, tables with a shelf and tables "
            "that lift to become a work surface."
        ),
        "teasers": [
            "Height is commonly about the same as the sofa seat, or slightly lower, around 35-45 cm.",
            "Leave about 40-50 cm between the table and the sofa so you can reach it and still walk by.",
            "Check how the top handles heat, water and scratches, and what the edges are like at knee height.",
        ],
        "intro": (
            "A coffee table is small and often the centre of a room, so proportion and use matter more than "
            "decoration. These are the things worth settling before you choose one. The numbers are common rules "
            "of thumb, not fixed rules."
        ),
        "sections": [
            ("Height", [
                "A coffee table is commonly about the height of the sofa seat or a little lower, around 35-45 cm. Much higher and it is awkward to reach over; much lower and it is hard to put anything on or lean forward to.",
                "If you eat or work at it, a slightly higher table is more comfortable.",
            ]),
            ("Size and room", [
                "A common guide is a table about two thirds the length of the sofa, so it does not dominate.",
                "Leave about 40-50 cm between the table and the sofa, so you can reach it and still walk past.",
                "A round or oval table is kinder to a small room and to knees; a rectangular one holds more.",
                "Nests of two or three tables can be pulled apart and tucked away when you need the floor.",
            ]),
            ("Top and material", [
                "Solid wood can be sanded and refinished. Veneer is more stable but allows less refinishing. Stone and ceramic resist heat and scratches but are heavy and can chip at the edges. Glass shows every mark.",
                "Oiled wood marks more easily but is easier to repair in one spot. A lacquered finish resists marks and is harder to repair.",
                "Whatever the top, use coasters under hot cups and wipe standing water, especially on wood and untreated stone.",
            ]),
            ("Edges and safety", [
                "A coffee table sits at knee and shin height. Rounded or softened edges and corners are kinder where children or pets play.",
                "Glass tops should be toughened or laminated safety glass.",
            ]),
            ("Storage and use", [
                "A shelf or a drawer adds storage but also fills up. Consider whether you want a clear surface to put things on.",
                "A table that raises or tilts is useful for work and meals, but check how stable it is when raised.",
            ]),
            ("Questions worth asking the maker", [
                "What are the exact height and top dimensions? What is the top made of and how is it finished? Is the glass safety glass? Is the top heat-resistant? What are the delivery and return terms?",
            ]),
        ],
        "sources": [FSC, PEFC, ("Safety glass", "https://en.wikipedia.org/wiki/Safety_glass"), SWAN, GREEN_CLAIMS],
    },
    {
        "slug": "side-tables",
        "group": "Furniture",
        "noun": "side tables",
        "title": "Side tables",
        "edit_slug": "side-tables",
        "summary": "Height, footprint, stability and materials for the small table beside a sofa, chair or bed.",
        "about": (
            "A side table is the small surface beside a sofa, an armchair or a bed: somewhere to rest a drink, a "
            "lamp or a book without getting up. It is often the smallest piece in the room and the one that is "
            "moved the most. They range from tall slim tables and round pedestals to trays on legs, drum shapes "
            "and tables that slide over a chair arm."
        ),
        "teasers": [
            "Match the height to the arm of the chair or sofa, commonly about the same or a little lower.",
            "Check the top is big enough for what you will put on it, and whether it is stable if bumped.",
            "A lamp on a side table needs a base that will not tip, and room for the cable.",
        ],
        "intro": (
            "A side table does one small job well, and the details decide whether it does. These are the things "
            "worth settling before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Height", [
                "A side table is commonly about the same height as the arm of the chair or sofa, or a little lower, so you can reach it without leaning.",
                "Beside a bed, the top is commonly about level with the mattress or slightly above it.",
            ]),
            ("Top and footprint", [
                "Decide what goes on it: a cup and a book need a smaller top than a lamp, a plant and a tray. A top around 40-50 cm across is common.",
                "A pedestal or a wide base steadies a tall table; a slim leg is lighter and easier to move but tips more easily.",
                "Rounded corners are kinder in tight spaces and near children.",
            ]),
            ("Stability", [
                "Press down on the edge of the top. A table that wobbles or tips when you rest a hand on it is a table you will stop using.",
                "Uneven floors and soft carpets affect stability; look for adjustable feet.",
            ]),
            ("Materials", [
                "Solid wood can be refinished; stone and ceramic resist heat and scratches but are heavy; metal can dent or scratch; glass shows marks.",
                "Whatever the top, use a coaster under hot cups and wipe standing water.",
            ]),
            ("With a lamp", [
                "A lamp on a side table needs a stable surface, space for its base and a route for the cable that does not run across the walkway.",
            ]),
            ("Questions worth asking the maker", [
                "What are the exact height and top dimensions? What is the top made of and how is it finished? Are there adjustable feet? What are the delivery and return terms?",
            ]),
        ],
        "sources": [FSC, PEFC, SWAN, GREEN_CLAIMS],
    },
    {
        "slug": "cabinets",
        "group": "Furniture",
        "noun": "cabinets",
        "title": "Cabinets",
        "edit_slug": "cabinets",
        "summary": "Size, doors and drawers, fixing to the wall, materials and care for storage you live with.",
        "about": (
            "A cabinet is storage that stays in view, so how it opens, how it stands and what it is made of "
            "matter as much as what it holds. They range from low units and tall display cabinets to glazed "
            "cases, cupboards on legs and wall-mounted cabinets, with doors, drawers or both."
        ),
        "teasers": [
            "Measure the space and the clear room needed for doors and drawers to open.",
            "Tall or top-heavy cabinets should be fixed to the wall to prevent tipping.",
            "Check the hinges, runners and shelves, and whether the shelves are adjustable.",
        ],
        "intro": (
            "A cabinet is a piece you open every day, so the parts that move are the parts that matter. These are "
            "the things worth settling before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Size and placement", [
                "Measure the wall and the space in front of it, including the room doors and drawers need to open fully.",
                "Check the depth: deep cabinets hold more but stick out into the room; shallow ones suit hallways.",
                "Check the plinth or legs against skirting boards and uneven floors; adjustable feet help.",
            ]),
            ("Doors and drawers", [
                "Hinged doors need clear space in front; sliding doors do not. Soft-close hinges and runners are a common feature, but ask whether they can be replaced.",
                "Drawers on full-extension runners show everything at the back; check the weight a drawer is built to carry.",
                "A push-to-open door has no handle and needs a gentle touch; check how it works if you have little hands or full arms.",
            ]),
            ("Fixing to the wall", [
                "A tall or top-heavy cabinet can tip if drawers are pulled out or a child climbs it. Fix it to the wall with fittings that suit your wall (concrete, brick, studs or plasterboard).",
                "A wall-mounted cabinet needs fixings rated for the load and the wall, and often a mounting rail; the weight of what it will hold matters.",
            ]),
            ("Inside", [
                "Adjustable shelves let you change the layout later. Check the shelf's span and the weight it can take.",
                "Glass shelves and doors should be toughened or laminated safety glass.",
            ]),
            ("Materials and finish", [
                "Solid wood can be refinished; veneer over a core is more stable but allows less refinishing. Lacquered surfaces resist marks and are harder to repair.",
                "Check whether the back panel and inside are finished, and whether any smell from new finishes fades.",
            ]),
            ("Questions worth asking the maker", [
                "What are the exact dimensions and clear opening room? What is the cabinet made of and how is it finished? How is it fixed to the wall? Are the shelves adjustable? Are spare hinges and runners available? What are the delivery and return terms?",
            ]),
        ],
        "sources": [FSC, PEFC, ("Safety glass", "https://en.wikipedia.org/wiki/Safety_glass"), KONSUMENTVERKET, SWAN, GREEN_CLAIMS],
    },
    {
        "slug": "rugs",
        "group": "Objects",
        "noun": "rugs",
        "title": "Rugs",
        "edit_slug": "rugs",
        "summary": "Size and placement, pile and fibre, backing, care and the questions to ask about how a rug was made.",
        "about": (
            "A rug does more than cover a floor: it warms a room, softens the sound in it and ties a group of "
            "furniture together. The size and the position matter more than the pattern. They range from hand-knotted "
            "and hand-woven rugs to tufted, flat-woven and machine-made ones, in wool, cotton, jute, silk, "
            "synthetic fibres and blends."
        ),
        "teasers": [
            "Size matters most: in a living room, the front legs of the sofa and chairs commonly sit on the rug.",
            "Pile height and fibre decide how it feels underfoot and how it wears and cleans.",
            "Ask how the rug was made and by whom; some certifications cover this, and each covers one aspect only.",
        ],
        "intro": (
            "A rug is easy to choose too small, and hard to return once it is rolled out. These are the things "
            "worth settling before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Size and placement", [
                "Under a dining table, the rug commonly extends about 60-70 cm beyond the table on every side, so chairs stay on it when pulled out.",
                "In a living room, a common guide is that at least the front legs of the sofa and chairs sit on the rug; a rug that floats in the middle of the room tends to make it feel smaller.",
                "In a bedroom, a rug usually extends beyond both sides of the bed, or sits under the lower two thirds of it.",
                "Measure the room and mark the rug's outline on the floor with tape before you decide.",
            ]),
            ("Pile and weave", [
                "Pile height decides the feel: a high pile is soft and holds dust; a low or flat weave is easier to clean and suits chairs on wheels and high-traffic areas.",
                "Hand-knotted rugs are made knot by knot and last for decades; tufted rugs are made faster with a gun and a backing; flat-weaves are woven without pile. Ask which one you are looking at.",
            ]),
            ("Fibres", [
                "Wool is resilient, warm and naturally dirt-resistant, and sheds a little at first. Cotton is easy to wash. Jute and sisal are coarse underfoot and suit rooms where you are not often barefoot. Silk is delicate. Synthetic fibres resist stains and moisture but wear differently.",
                "A rug in a hallway or a kitchen needs to be tougher than one beside a bed.",
            ]),
            ("Underlay and floor", [
                "A rug pad stops slipping, adds cushioning and protects the floor. Check that the pad is made for your floor: some can mark vinyl or lacquered wood.",
                "On underfloor heating, check that the rug and the pad are suitable.",
            ]),
            ("Care", [
                "Vacuum regularly, turn the rug now and then so it wears evenly, and deal with spills quickly by blotting rather than rubbing.",
                "Hand-knotted and silk rugs are best cleaned by a specialist.",
            ]),
            ("How it was made", [
                "Ask where the rug was woven, by whom and under what conditions. Certifications such as GoodWeave focus on child labour and labour conditions in rug weaving; OEKO-TEX focuses on substances in textiles. Each covers one aspect and is not a verdict on the whole product.",
            ]),
            ("Questions worth asking the maker", [
                "What are the exact dimensions and pile height? What is the rug made of, and how was it made? Can it be used with underfloor heating? How should it be cleaned? What are the delivery and return terms?",
            ]),
        ],
        "sources": [OEKO_TEX, GOODWEAVE, SWAN, GREEN_CLAIMS],
    },
    {
        "slug": "mirrors",
        "group": "Objects",
        "noun": "mirrors",
        "title": "Mirrors",
        "edit_slug": "mirrors",
        "summary": "Size, height, glass, hanging and placement for mirrors that light, widen and finish a room.",
        "about": (
            "A mirror does a practical job, helping you see yourself, and a spatial one, because it bounces light "
            "and doubles a view. Where it hangs and what it reflects matter as much as the frame. They range from "
            "full-length floor mirrors and tall leaning mirrors to wall mirrors in round, oval and arched shapes, "
            "mirrors with shelves or lights, and small tabletop mirrors."
        ),
        "teasers": [
            "Hang it so the centre sits at about eye level, commonly around 145-155 cm from the floor.",
            "Think about what it will reflect: a window brings light in; clutter looks twice as big.",
            "A heavy mirror needs fixings rated for its weight and the wall, and often two people to hang it.",
        ],
        "intro": (
            "A mirror is as much about what it reflects as about how it looks. These are the things worth settling "
            "before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Size and height", [
                "Hang a wall mirror so its centre is at about eye level, commonly around 145-155 cm from the floor. A mirror above a console, sideboard or basin is commonly a little narrower than the piece below it.",
                "For checking an outfit, a full-length mirror is about 150-180 cm tall; a floor mirror that leans needs a stable angle and a non-slip foot.",
            ]),
            ("Placement and light", [
                "A mirror opposite or beside a window brings daylight further into the room; one opposite a bright light can glare at night.",
                "Think about what it will reflect. A view, a lamp or a plant doubles well; a bin or a pile of cables does not.",
                "In a hallway, a mirror helps with a last check on the way out; in a bathroom, check the lighting from the sides, not only from above.",
            ]),
            ("The glass", [
                "Thin glass can show slight distortion. Judge the reflection from a distance, not only up close.",
                "Antique or aged mirrors have a deliberately uneven surface; that is a look, not a defect.",
                "Mirrors in children's rooms, near stairs or in a busy hallway should be made from safety glass or have a safety backing film.",
            ]),
            ("Hanging and fixing", [
                "Mirrors can be heavy. Check the weight and use fixings suited to your wall (concrete, brick, studs or plasterboard); often two people hang it.",
                "A leaning mirror is easier to place but can slip; ask about anti-slip feet and a wall strap.",
                "Bathrooms and damp rooms need a mirror made for damp: look for edges and a back that are protected from moisture.",
            ]),
            ("Care", [
                "Clean with a soft cloth and a glass cleaner sprayed on the cloth, not on the mirror, so liquid does not run behind the edge.",
            ]),
            ("Questions worth asking the maker", [
                "What are the exact dimensions and weight? Is the glass safety glass or backed with a safety film? How is it hung, and what fixings are included? Is it suitable for a damp room? What are the delivery and return terms?",
            ]),
        ],
        "sources": [("Mirrors, how they work and are made", "https://en.wikipedia.org/wiki/Mirror"), ("Safety glass", "https://en.wikipedia.org/wiki/Safety_glass"), KONSUMENTVERKET, GREEN_CLAIMS],
    },
]

ERGONOMICS = ("Ergonomics, the study of how people fit the things they use", "https://en.wikipedia.org/wiki/Human_factors_and_ergonomics")
WORK_ENV = ("Work environment advice from the Swedish Work Environment Authority", "https://www.av.se/en/")

GUIDES += [
    {
        "slug": "stools",
        "group": "Furniture",
        "noun": "stools",
        "title": "Stools",
        "edit_slug": "stools",
        "summary": "Height, seat shape, stability and materials for the small seat that does many jobs.",
        "about": (
            "A stool is the most flexible seat in a home: at a table, beside a bed, in a hallway to put on shoes, "
            "at a worktop or as an extra surface. With no back it takes little space and is easy to move. They "
            "range from low three-legged stools and stacking stools to padded seats, step stools and tall "
            "stools for counters."
        ),
        "teasers": [
            "Match the height to the surface: commonly around 45 cm at a dining table, 60-65 cm at a counter.",
            "Check the seat shape and size, because with no back the seat does all the work.",
            "Three legs sit steadier on an uneven floor; four need a level one.",
        ],
        "intro": (
            "A stool does many jobs, so first decide which one it is for. These are the things worth settling "
            "before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Height", [
                "A stool at a dining table is commonly about 45 cm to the seat. At a kitchen counter, around 60-65 cm; at a taller bar, around 70-75 cm. Leave about 25-30 cm between the seat and the underside of the surface.",
                "A low stool, around 30-40 cm, works as a perch, a footrest or a side table.",
            ]),
            ("Seat", [
                "With no back, the seat does all the work: a shaped or slightly dished seat is more comfortable for longer than a flat one.",
                "A seat around 30-35 cm across suits short sittings; a wider one suits longer.",
                "A padded seat is softer; check whether the cover can be replaced.",
            ]),
            ("Stability", [
                "Three legs sit steadily on an uneven floor, while four need a level one. Legs that splay outward are harder to tip.",
                "A footrest ring helps at counter height, and also braces the legs.",
                "Check the weight rating if more than one person will use it, or if it will be used as a step.",
            ]),
            ("Materials and care", [
                "Solid wood can be refinished. Metal can scratch or dent; powder-coated finishes can chip. Stone, ceramic and concrete are heavy and can chip at the edges.",
                "Leather and fabric padding age differently; ask whether the cover can be replaced.",
                "Check the feet. Glides or felt pads protect floors; rubber feet may mark some floors.",
            ]),
            ("Stacking and storing", [
                "Stacking stools save space but add wear where they touch. Check how many can be stacked and whether they mark each other.",
            ]),
            ("Questions worth asking the maker", [
                "What is the exact seat height and width? What is the weight rating? Are the feet replaceable? Can the seat cover be replaced? What are the delivery and return terms?",
            ]),
        ],
        "sources": [FSC, PEFC, ERGONOMICS, SWAN, GREEN_CLAIMS],
    },
    {
        "slug": "bar-stools",
        "group": "Furniture",
        "noun": "bar stools",
        "title": "Bar stools",
        "edit_slug": "bar-stools",
        "summary": "Counter and bar height, footrests, backs, swivel and materials for tall seats.",
        "about": (
            "A bar stool lifts you to counter or bar height, so the choice starts with a measurement. A stool that "
            "is too tall or too low is uncomfortable however good it looks. They range from backless stools and "
            "stools with a low back to full chairs on tall legs, in fixed, swivel and adjustable-height versions."
        ),
        "teasers": [
            "Measure the counter, not the room: counter height is commonly 85-95 cm, bar height 105-115 cm.",
            "Leave about 25-30 cm between the seat and the underside of the surface.",
            "Look for a footrest, a stable base and floor protection.",
        ],
        "intro": (
            "A bar stool is chosen from a measurement: the height of the surface it sits at. These are the things "
            "worth settling before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Seat height", [
                "Measure from the floor to the underside of the counter or bar. Leave about 25-30 cm between the seat and that surface.",
                "Counter height is commonly 85-95 cm, which suits a seat of about 60-65 cm. Bar height is commonly 105-115 cm, which suits about 70-80 cm.",
                "An adjustable-height stool covers different surfaces, but check how the mechanism wears and whether it can be replaced.",
            ]),
            ("Back, arms and swivel", [
                "A backless stool tucks fully under the counter and suits short stays. A back supports longer sitting; a low back is a compromise.",
                "A swivel makes getting in and out easy and suits tight spaces; a fixed stool is steadier. Look for a swivel that stops or returns.",
                "Check the width of the seat and the space between stools; allow around 60-65 cm each along the counter.",
            ]),
            ("Footrest and stability", [
                "A footrest matters at this height: with none, feet dangle. A ring or a rail also braces the legs.",
                "Check the base. A wide base resists tipping; a narrow base needs more care. Check the weight rating.",
            ]),
            ("Floors and noise", [
                "Fit glides or felt pads that suit the floor. Some feet mark vinyl or lacquered floors, and some stools scrape when pulled out.",
            ]),
            ("Materials and care", [
                "Solid wood can be refinished. Metal frames can scratch; powder-coated finishes can chip. Upholstery and leather age differently, and a wipeable seat suits a kitchen.",
            ]),
            ("Questions worth asking the maker", [
                "What is the exact seat height, and is it adjustable? What is the weight rating? Which feet are fitted, and can they be replaced? Can the seat cover be replaced? What are the delivery and return terms?",
            ]),
        ],
        "sources": [("Bar stools", "https://en.wikipedia.org/wiki/Bar_stool"), FSC, PEFC, ERGONOMICS, GREEN_CLAIMS],
    },
    {
        "slug": "beds",
        "group": "Furniture",
        "noun": "beds",
        "title": "Beds",
        "edit_slug": "beds",
        "summary": "Size, base, headboard, materials and assembly for the piece you spend a third of your life on.",
        "about": (
            "A bed frame is the biggest piece in a bedroom, and the mattress and base inside it matter as much as "
            "the look. Standards for size differ by country, so measuring both room and mattress is the first step. "
            "Frames range from simple platforms and slatted beds to upholstered beds, four-posters, daybeds and "
            "beds with storage."
        ),
        "teasers": [
            "Mattress sizes differ by country (for example 160 x 200 cm is common in Sweden); check the frame fits your mattress.",
            "Check how the base supports the mattress: slats, a solid platform or a sprung base.",
            "Measure the room, the door and the stairwell, as a bed has to get into the room.",
        ],
        "intro": (
            "A bed is a frame around a mattress, and the two have to fit. These are the things worth settling "
            "before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Size and fit", [
                "Mattress sizes differ between countries. In Sweden, for example, 160 x 200 cm is a common double; elsewhere a king or queen size is different. Check the frame's internal dimensions against the mattress you will use.",
                "Allow space around the bed: around 60-70 cm on each side makes it easy to walk past and to make the bed.",
                "Check the overall height of the frame and the headboard if you will have a window, a wall light or a shelf behind it.",
            ]),
            ("Base and support", [
                "A slatted base lets the mattress breathe and is common; the slats' spacing and number matter for some mattresses, so check what the mattress maker requires.",
                "A solid platform or a sprung base feels different and suits different mattresses. Ask which the frame is designed for.",
                "A double bed benefits from a centre support, so the base does not sag.",
            ]),
            ("Headboard and design", [
                "A headboard protects the wall and gives something to lean on; a low or no headboard suits a small room or a bed against a wall.",
                "Upholstered frames are soft and quiet; ask whether the cover can be removed or replaced.",
            ]),
            ("Storage", [
                "Drawers or a lifting base add storage but also weight and parts that move. Check how easily they open and how much space they need beside or at the end of the bed.",
            ]),
            ("Materials and construction", [
                "Solid wood frames can be tightened and refinished; check how the joints are made and whether the bed can be taken apart and put together again if you move.",
                "Check the wood's origin and finish if that matters to you, and the finish if the bed is for a child.",
            ]),
            ("Delivery and assembly", [
                "Measure the doors, stairs and turns the bed has to pass. Many frames arrive flat-packed or in sections.",
                "Check whether assembly is included and what tools are needed.",
            ]),
            ("Questions worth asking the maker", [
                "What are the internal dimensions? What base is included, and what support does it give? Can it be taken apart? Is assembly included? What are the delivery and return terms?",
            ]),
        ],
        "sources": [("Mattresses, types and sizes", "https://en.wikipedia.org/wiki/Mattress"), FSC, PEFC, OEKO_TEX, SWAN, GREEN_CLAIMS],
    },
    {
        "slug": "desks",
        "group": "Furniture",
        "noun": "desks",
        "title": "Desks",
        "edit_slug": "desks",
        "summary": "Height, depth, cables, storage and light for the surface you work at every day.",
        "about": (
            "A desk is a work surface you use for hours, so its height, depth and edges matter more than its looks. "
            "Where it stands, the light it gets and the cables it has to hide are part of the choice. They range "
            "from slim writing desks and console desks to large work desks, standing and height-adjustable desks "
            "and desks with drawers."
        ),
        "teasers": [
            "Desk height is commonly about 72-75 cm; check your chair, elbows and screen.",
            "Allow depth for a screen: around 60-80 cm is common.",
            "Check where cables, sockets and light will go before you choose.",
        ],
        "intro": (
            "A desk is the surface you work at, so the details that fit your body matter. These are the things "
            "worth settling before you choose one. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Height and posture", [
                "Desk height is commonly about 72-75 cm. Check it against your chair: your forearms should rest on the surface with the elbows at about a right angle.",
                "The top of a screen should be about at eye level or slightly below. A laptop usually needs a stand or a separate screen to get this right.",
                "A height-adjustable desk lets you stand part of the time; check the range, the motor's noise and whether it remains stable when raised.",
            ]),
            ("Size and depth", [
                "A depth of around 60-80 cm is common; a deeper desk suits one or two screens or paper work. A width of around 120-160 cm suits one person.",
                "Check the space under the top for your legs and the chair, including any drawers or a frame beam.",
            ]),
            ("Cables and power", [
                "Plan where the cables will go: a cut-out, a tray, a channel or a leg that can carry them. Check the distance to the socket.",
                "A desk against a wall may be fine; a desk in the middle of a room needs a different solution.",
            ]),
            ("Storage", [
                "Drawers add storage and weight; a shelf or a tray keeps things off the surface. A clean desk often works better with a place for what you need every day.",
            ]),
            ("Light", [
                "Place a desk so that daylight comes from the side rather than from behind or in front of the screen. A lamp, set on the side opposite your writing hand, reduces shadows.",
            ]),
            ("Materials and care", [
                "Solid wood can be refinished; laminate and veneer resist wear in different ways. Glass shows marks, and metal can scratch.",
                "A top with a soft finish is kinder to wrists and a mouse; a hard one is easier to clean. A desk mat can help.",
            ]),
            ("Questions worth asking the maker", [
                "What are the exact height and top dimensions? If adjustable, what is the range and weight limit? Where do cables run? What is the top made of and how is it finished? What are the delivery and return terms?",
            ]),
        ],
        "sources": [ERGONOMICS, WORK_ENV, FSC, PEFC, GREEN_CLAIMS],
    },
    {
        "slug": "shelving",
        "group": "Furniture",
        "noun": "shelving",
        "title": "Shelving",
        "edit_slug": "shelving",
        "summary": "Load, spacing, fixing to the wall and materials for shelves that hold what you own.",
        "about": (
            "Shelving holds what you own, so the weight it takes and how it is fixed matter before the look. "
            "Open shelves show everything; deeper or taller ones give more room but need more care. They range "
            "from wall-mounted shelves and rails to freestanding bookcases, ladder shelves and modular systems "
            "that grow."
        ),
        "teasers": [
            "Check the load per shelf: books are heavy, commonly around 20-25 kg per metre of shelf.",
            "Tall or freestanding shelving should be fixed to the wall to stop it tipping.",
            "Wall-mounted shelves need fixings that suit your wall (concrete, brick, studs or plasterboard).",
        ],
        "intro": (
            "Shelves carry weight, and a shelf that bends or a unit that tips is more than a nuisance. These are the "
            "things worth settling before you choose some. The numbers are common rules of thumb, not fixed rules."
        ),
        "sections": [
            ("Load and span", [
                "Books are heavy, commonly around 20-25 kg per metre of shelf. Check the load the maker states for a shelf, and for the whole unit.",
                "A long span between supports bends over time, especially in thin boards. A shelf around 80 cm or shorter is stiffer; for a longer span, check the thickness and any reinforcement.",
                "Heavy things go on lower shelves.",
            ]),
            ("Fixing to the wall", [
                "Tall or freestanding shelving can tip if a child climbs it or the load is uneven. Fix it to the wall with fittings that suit your wall.",
                "Wall-mounted shelves need fixings rated for the load and the wall: concrete, brick, studs and plasterboard each need different ones. Check what is included, and whether it suits your wall.",
                "A rail or track system adds adjustment; check how it is fixed and how much weight it carries.",
            ]),
            ("Depth and spacing", [
                "A depth of about 25-30 cm suits books; about 35-40 cm suits storage boxes and larger objects. Deeper shelves are harder to reach into.",
                "Adjustable shelves let you change the layout later; check how they are held in place.",
            ]),
            ("Open or closed", [
                "Open shelving shows everything, which suits objects and books, and collects dust. Doors or boxes hide the rest.",
            ]),
            ("Materials and care", [
                "Solid wood can be refinished; veneer resists warping better but allows less refinishing. Metal and glass suit different looks; glass shelves should be toughened or laminated safety glass.",
                "Check the edges and the finish where things will be put on and taken off.",
            ]),
            ("Modular and growing systems", [
                "Modular systems let you add to a unit over time. Check that parts are still being made, and that new ones will match.",
            ]),
            ("Questions worth asking the maker", [
                "What load does each shelf take, and the whole unit? How is it fixed to the wall, and what fixings are included? Are the shelves adjustable? Can I add parts later? What are the delivery and return terms?",
            ]),
        ],
        "sources": [KONSUMENTVERKET, ("Safety glass", "https://en.wikipedia.org/wiki/Safety_glass"), FSC, PEFC, GREEN_CLAIMS],
    },
    {
        "slug": "sideboards",
        "group": "Furniture",
        "noun": "sideboards",
        "title": "Sideboards",
        "edit_slug": "sideboards",
        "summary": "Size, doors and drawers, legs, wall fixing and finish for the long, low piece of storage.",
        "about": (
            "A sideboard is long, low storage that doubles as a surface: for a lamp, a vase, a record player or the "
            "serving dishes at dinner. It often anchors a wall, so proportion and the space in front of it matter. "
            "They range from slim sideboards on legs to wide, low units with sliding doors, drawers or both, in "
            "wood, lacquer, metal and stone."
        ),
        "teasers": [
            "Measure the wall and the room in front of it, including how far doors and drawers open.",
            "Height is commonly about 70-90 cm; a lower unit suits a low sofa or a window.",
            "Check the load rating, the leg or plinth, and whether it can be fixed to the wall.",
        ],
        "intro": (
            "A sideboard is storage you open every day and a surface you put things on, so how it moves and how it "
            "stands matter. These are the things worth settling before you choose one. The numbers are common rules "
            "of thumb, not fixed rules."
        ),
        "sections": [
            ("Size and placement", [
                "Measure the wall and the room in front of it, including the space doors and drawers need to open. Sliding doors need less space in front.",
                "Height is commonly about 70-90 cm. A lower sideboard suits a space under a window or behind a low sofa; a higher one suits a dining room.",
                "Depth is commonly about 40-50 cm; a shallower one suits a hallway.",
            ]),
            ("Doors and drawers", [
                "Check what the doors and drawers do: hinged doors, sliding doors and push-to-open each feel different. Soft-close is common; ask whether the parts can be replaced.",
                "Drawers on full-extension runners show everything at the back. Check the weight a drawer is built to carry.",
            ]),
            ("Legs, plinth and floor", [
                "Legs let you see the floor and clean beneath; a plinth looks heavier and is steadier. Check adjustable feet for an uneven floor.",
                "A heavy sideboard needs felt or glides that protect the floor.",
            ]),
            ("Fixing to the wall", [
                "A tall or deep sideboard can tip, and a wall-mounted one needs fixings that suit your wall. Check what the maker supplies and the load it is rated for.",
            ]),
            ("Top and finish", [
                "A sideboard top takes hot dishes, lamps and drinks. Solid wood can be refinished; lacquered tops resist marks and are harder to repair; stone resists heat and scratches but is heavy.",
                "Use coasters and trivets whatever the top.",
            ]),
            ("Cables and use as a media unit", [
                "If it will hold a television or speakers, check for cable cut-outs and for ventilation, and ask whether glass or perforated doors suit remote controls.",
            ]),
            ("Questions worth asking the maker", [
                "What are the exact dimensions and clear opening room? What load does the top and each shelf take? How is it fixed to the wall? What is the top made of and how is it finished? What are the delivery and return terms?",
            ]),
        ],
        "sources": [KONSUMENTVERKET, FSC, PEFC, SWAN, GREEN_CLAIMS],
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


# Types that have no buying guide (yet) still get a short "About" block and the one-line preamble (2026-10-15). Plain description of the
# type and its range; no claims about makers; the data sentence (countries, independent makers, new pieces) is added from the catalogue.
TYPE_ABOUT = {
    "wall-lamps": ("wall lamps",
        "A wall lamp lights from the side of a room instead of from the ceiling or a table. That frees the floor and puts the light where it is "
        "used: beside a bed, over a mirror, along a hallway or above a desk. They range from small fixed sconces and swing-arm reading lights to "
        "long linear wall lights, and from lamps wired into the wall to plug-in designs with a visible cable."),
    "ceiling-lamps": ("ceiling lamps",
        "A ceiling lamp is fixed straight to the ceiling with no drop, which makes it the choice for low rooms, hallways and kitchens where a "
        "hanging lamp would be in the way. They include flush mounts and surface mounts, from simple discs and domes to sculpted shades and "
        "multi-arm fittings."),
    "chandeliers": ("chandeliers",
        "A chandelier is a ceiling lamp with several arms, lights or elements, made to be looked at as much as to give light. Classic crystal and "
        "glass designs sit beside contemporary ones in metal, blown glass, paper and ceramic, in sizes from a compact cluster over a table to a "
        "centrepiece for a stairwell."),
    "garden-chairs": ("garden and outdoor chairs",
        "Garden and outdoor chairs are made to stay outside for part of the year, so the material matters: teak and other hardwoods, powder-coated "
        "aluminium and steel, woven synthetic fibre, stone and weather-resistant fabric. They range from folding bistro chairs to deep lounge "
        "chairs and dining chairs for a terrace table."),
    "side-chairs": ("side chairs",
        "A side chair is a lighter chair that is not tied to one table. It can stand against a wall in a hallway, sit at a desk or add a seat in a "
        "living room, and many are also used at dining tables. They range from slim wood and metal frames to upholstered seats, with and without arms."),
    "folding-chairs": ("folding and stacking chairs",
        "Folding and stacking chairs are designed to be put away: a folding chair flattens against a wall and stacking chairs sit in a pile. They suit "
        "small homes, extra guests, studios and cafés. They range from classic wooden folding chairs to moulded stacking chairs and light metal designs."),
    "kids-chairs": ("kids' chairs",
        "Kids' chairs are made smaller and lower than adult chairs, so a child can sit with their feet on the floor. They include scaled-down versions "
        "of well-known chairs, stackable chairs for a play room, stools and high chairs, in wood, plastic and upholstery."),
    "office-chairs": ("office and desk chairs",
        "Office and desk chairs are made to be sat in for hours: most swivel and adjust in height, and many also tilt or have adjustable arms and "
        "backs. The page also lists desk chairs for the home, from task chairs with mesh backs to upholstered designs that look at home in a living room."),
    "dining-chairs": ("dining chairs",
        "A dining chair is sat in for a meal and often for the hour after it, so seat height, depth and back support matter as much as looks. They "
        "range from slim wood and cane chairs to upholstered and moulded designs, with and without arms, and many come in several finishes."),
    "benches": ("benches",
        "A bench seats two or more people along one length. It works at a dining table in place of chairs, at the end of a bed, in a hallway for shoes "
        "and coats, or against a wall as extra seating. They range from solid wood and stone benches to upholstered and outdoor designs, some with storage."),
    "footstools": ("footstools",
        "A footstool is a low seat or rest for the feet, made as the companion to an armchair or lounge chair. Some are sold as a matching piece; others "
        "are stand-alone designs in leather, wool, wood or padded fabric that also work as an extra seat or a small table."),
    "ottomans-and-poufs": ("ottomans and poufs",
        "Ottomans and poufs are low, soft seats without a back. They are used as extra seating, as a footrest or, with a tray on top, as a small table. "
        "They range from round cushioned poufs in wool, leather and knit to large rectangular ottomans, some with a hinged lid and storage inside."),
    "console-tables": ("console tables",
        "A console table is a narrow table made to stand against a wall: in a hallway, behind a sofa or under a mirror. It holds keys, a lamp, a bowl or "
        "books without taking much floor space. They range from slim wood and metal designs to marble-topped and sculptural ones, with and without drawers."),
    "bedside-tables": ("bedside tables",
        "A bedside table holds what you reach for at night: a lamp, a book, a glass of water, a phone. They are made to sit close to the height of the "
        "mattress. They range from open tables and trays on legs to cabinets with drawers or doors, and wall-hung designs that leave the floor clear."),
    "outdoor-tables": ("outdoor tables",
        "Outdoor tables are made for terraces, balconies and gardens, in materials that stand up to rain, sun and frost: hardwood, aluminium, steel, "
        "stone, ceramic and weather-resistant resin. They range from small bistro tables to long dining tables, and from low tables for a lounge group to "
        "side tables."),
    "bar-tables": ("bar tables",
        "A bar table is taller than a dining table, made to be used standing or with bar stools or counter-height chairs. It suits kitchen islands, small "
        "flats and places for entertaining. They range from small round pub-style tables to long counters, in wood, metal and stone."),
    "candles": ("candles",
        "The candles here range from scented candles in glass, ceramic and tin to plain taper and pillar candles, and candles sold as objects in their "
        "own right. Scent, burn time and wax differ from maker to maker, so each piece links to the maker's own page for the details."),
    "glass": ("glassware",
        "This page gathers glassware: drinking glasses, wine and water glasses, tumblers, carafes and jugs, made by hand or machine. They range from "
        "thin, mouth-blown glass to heavy pressed and coloured glass, and from single glasses to sets."),
    "vases": ("vases",
        "A vase holds flowers, branches or dried stems, and is often an object worth looking at without them. They range from small bud vases to tall "
        "floor vases, in ceramic, glass, metal and stone, and from smooth thrown shapes to hand-built and sculptural forms."),
    "bowls": ("bowls",
        "Bowls work on the table and on the shelf: serving and salad bowls, soup and cereal bowls, fruit bowls, and bowls that are simply objects. They "
        "range from thrown ceramic and glass to wood, metal and stone, in sizes from a small dish to a wide centrepiece."),
    "plates": ("plates",
        "Plates range from dinner and side plates to platters, serving plates and decorative wall plates. They are made in porcelain, stoneware, "
        "earthenware and glass, plain or patterned, and are often sold singly as well as in sets."),
    "trays": ("trays",
        "A tray carries, serves and gathers: breakfast and drinks, small things on a table, or keys and post by the door. They range from small "
        "catch-all trays to large serving trays, in wood, metal, ceramic, leather and woven materials."),
    "cushions": ("cushions",
        "Cushions add comfort and colour to a sofa, bed or chair. They range from wool, linen, cotton and velvet to knitted, quilted and printed "
        "designs, and from square and rectangular to round and bolster shapes. Some are sold as a cover only, without the inner."),
    "blankets": ("blankets and throws",
        "Blankets and throws are for the sofa, the end of a bed or a cold evening. They range from wool, mohair and cashmere to cotton, linen and "
        "recycled fibres, in woven, knitted and quilted forms, and from plain to patterned designs."),
}
