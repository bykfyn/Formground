"""
The Work taxonomy and the "browse by type" menu (2026-10-04).

Three top-level categories (Furniture, Lighting, Objects - the same three the
home page tiles use), each made of the existing browse groups, each group of
type pages (/work/<slug>.html). One definition feeds the menu on the Work page,
the category pages (/work/furniture.html ...), the type pages' breadcrumbs and
the sitemap, so they can never disagree.

URL structure (decided 2026-10-04, see project-docs/Site_Patterns.md):
    /work.html               search + the menu
    /work/<category>.html    furniture | lighting | objects
    /work/<type>.html        the full catalogue of one type (pages: -2, -3 ...)
"""

import html

# category -> ordered browse groups (names as used in generate_browse_pages.BROWSE_CATEGORIES)
TAXONOMY = {
    # Houses first: the order of the home page bento (Houses on the left, then the others).
    # Houses are a category of Work like the rest (the project treats a house as a product,
    # an architect's output); their "types" are countries (the architect's country).
    "Houses": ["Houses"],
    "Furniture": ["Seating", "Tables and desks", "Storage, beds and mirrors"],
    "Lighting": ["Lighting"],
    "Objects": ["Objects", "Soft furnishings"],
}
CATEGORY_SLUGS = {name: name.lower() for name in TAXONOMY}  # furniture | lighting | objects
# Shown in the menu where a browse group's own name would read oddly under its category.
GROUP_LABELS = {"Lighting": "By type", "Objects": "Tableware, glass and candles", "Houses": "By country"}


def category_of_group(group):
    for cat, groups in TAXONOMY.items():
        if group in groups:
            return cat
    raise KeyError(group)


def entry_sort_key(e):
    """Types alphabetical, except a category's "New" entry (is_new) which always comes first."""
    return (not e.get("is_new"), e["title"].lower())


def category_entries(entries, category):
    """A category's types, plus its category-level "New" entry (is_new, which has no group of its own)."""
    return [e for e in entries
            if (e.get("category") == category if e.get("is_new") else category_of_group(e["group"]) == category)]


def category_total(entries, category):
    return sum(e["n"] for e in category_entries(entries, category) if not e.get("is_new"))


def _group_html(group, entries, current_slug, show_label=True):
    rows = []
    for e in sorted((x for x in entries if x["group"] == group), key=entry_sort_key):
        current = ' aria-current="page"' if e["slug"] == current_slug else ""
        rows.append(
            f'<li><a href="/work/{e["slug"]}.html"{current}>'
            f'<span class="work-menu-name">{html.escape(e["title"])}</span><span class="work-menu-n">{e["n"]:,}</span></a></li>'
        )
    items = "".join(rows)
    label = GROUP_LABELS.get(group, group)
    heading = f"<h3>{html.escape(label)}</h3>" if show_label else ""
    return f'<div class="work-menu-group">{heading}<ul>{items}</ul></div>'


def _new_row_html(e, current_slug):
    here = ' aria-current="page"' if e["slug"] == current_slug else ""
    return (f'<div class="work-menu-group work-menu-group--new"><ul><li><a href="/work/{e["slug"]}.html"{here}>'
            f'<span class="work-menu-name">New</span><span class="work-menu-n">{e["n"]:,}</span></a></li></ul></div>')


def render_menu(entries, open_category=None, current_slug=None, align="center", current_category=None, surprise="link"):
    """The menu: three category chips, each controlling a panel of groups and types.
    `current_category` marks the chip of the category the visitor is already in (type and
    category pages) - shown as selected, panel closed so the products stay above the fold;
    `open_category` starts a panel open (unused by the pages today)."""
    chips, panels = [], []
    # "Surprise me" is the last chip: an action, not a category. On the Work page it is a button
    # (search.js shuffles in place via its id); everywhere else a link to the Work page's shuffle.
    if surprise == "button":
        surprise_chip = ('<button type="button" class="work-menu-act" id="discover-chip" aria-label="Surprise me">'
                         '<i class="ti ti-arrows-shuffle" aria-hidden="true"></i><span>Surprise me</span></button>')
    else:
        surprise_chip = ('<a class="work-menu-act" href="/work.html" aria-label="Surprise me">'
                         '<i class="ti ti-arrows-shuffle" aria-hidden="true"></i><span>Surprise me</span></a>')
    for cat, groups in TAXONOMY.items():
        cid = f"wm-{CATEGORY_SLUGS[cat]}"
        is_open = cat == open_category
        chips.append(
            f'<button type="button" class="work-menu-cat{" is-current" if cat == current_category else ""}" aria-expanded="{"true" if is_open else "false"}" '
            f'aria-controls="{cid}">{html.escape(cat)} <i class="ti ti-chevron-down" aria-hidden="true"></i></button>'
        )
        body = "".join(_group_html(g, entries, current_slug) for g in groups)
        # "New" belongs to the category as a whole (Furniture / New), not to its first group (Seating): its own
        # row above the groups, styled like a type.
        new_row = "".join(_new_row_html(e, current_slug) for e in entries if e.get("is_new") and e.get("category") == cat)
        # The panel's title is the way up to the category page (an arrow marks it as a link). On the category's
        # own page it is plain text: it would only loop back to itself.
        if cat == current_category and current_slug in (None, CATEGORY_SLUGS[cat]):
            title = f'<strong>{html.escape(cat)}</strong>'
        else:
            title = (f'<a class="work-menu-title" href="/work/{CATEGORY_SLUGS[cat]}.html">'
                     f'<strong>{html.escape(cat)}</strong><span aria-hidden="true"> &rarr;</span></a>')
        panels.append(
            f'<div class="work-menu-panel" id="{cid}"{"" if is_open else " hidden"}>'
            f'<div class="work-menu-head">{title}</div>'
            f'{new_row}<div class="work-menu-groups">{body}</div></div>'
        )
    return (
        f'<nav class="work-menu{" work-menu--left" if align == "left" else ""}" aria-label="Browse by type">'
        f'<div class="work-menu-cats">{"".join(chips)}{surprise_chip}</div>{"".join(panels)}</nav>'
        '<noscript><style>.work-menu-panel[hidden]{display:block}</style></noscript>'
    )


MENU_START, MENU_END = "<!-- WORK-MENU:START -->", "<!-- WORK-MENU:END -->"


def inject_into_page(path, menu_html):
    """Write the menu between the markers of a hand-written page (frontend/work.html)."""
    import re
    text = path.read_text()
    block = f"{MENU_START}\n  {menu_html}\n  {MENU_END}"
    if MENU_START not in text:
        raise SystemExit(f"{path} has no {MENU_START} marker")
    new = re.sub(re.escape(MENU_START) + r".*?" + re.escape(MENU_END), lambda m: block, text, flags=re.S)
    if new != text:
        path.write_text(new)
    return new != text
