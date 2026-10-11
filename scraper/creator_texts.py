"""
Short, sourced text on creator pages (architects, makers, designers) and the profile Edits built from it.
Data: data/creator_texts.json, following docs/formground-creator-text-template.md:
  - 60-120 words in 2-3 paragraphs, plain and factual, paraphrased from the creator's own site or a named source
  - a facts block (never an "independent or established" line: that label is only used when it has been vouched for)
  - the sources, and a line saying the text changes or goes on request
Keys are "<group>:<page slug>" (group = architects | makers | designers). A paragraph may contain {count}, filled with
the live number of houses / pieces so it cannot go stale. Fields per entry: group, name, page_slug, website, paragraphs,
facts [[label, value]], sources [[label, url]], edit {slug, standfirst, hero, picks [image URLs]}.
"""

import datetime
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / "data" / "creator_texts.json"
CONTACT = "info@formground.com"
KIND = {"architects": "Architect", "makers": "Maker", "designers": "Designer"}

CREATOR_TEXT_CSS = """
  .creator-text { max-width: 640px; margin: 0 auto 36px; }
  .creator-text p { font-size: 15px; line-height: 1.65; color: var(--text-secondary); margin: 0 0 12px; }
  .creator-facts { display: grid; grid-template-columns: max-content 1fr; gap: 4px 18px; margin: 18px 0 14px;
    padding: 14px 0; border-top: 0.5px solid var(--border); border-bottom: 0.5px solid var(--border); font-size: 13px; }
  .creator-facts dt { color: var(--text-muted); }
  .creator-facts dd { margin: 0; color: var(--text-primary); }
  .creator-sources { font-size: 12px; color: var(--text-muted); line-height: 1.6; margin: 0; }
  .creator-sources a { color: var(--text-accent); }
"""


def today():
    """The build date. FG_TODAY (YYYY-MM-DD) overrides it, for tests and for previewing a scheduled day."""
    return datetime.date.fromisoformat(os.environ["FG_TODAY"]) if os.environ.get("FG_TODAY") else datetime.date.today()


def load_all():
    """Every entry in the data file, published or scheduled."""
    if not DATA_PATH.exists():
        return {}
    return json.loads(DATA_PATH.read_text())


def is_live(entry):
    """An entry with a "publish" date (YYYY-MM-DD) goes live on that day's build; with none it is live already."""
    return not entry.get("publish") or datetime.date.fromisoformat(entry["publish"]) <= today()


def load():
    """The entries that are live today. Everything the site builds (creator texts, profile Edits, hub tiles, the
    Creators page cards, the sitemap) reads this, so a scheduled profile appears on its publish day and not before."""
    return {k: v for k, v in load_all().items() if is_live(v)}


def get(group, page_slug):
    return load().get(f"{group}:{page_slug}")


def paragraphs(entry, count):
    return [p.replace("{count}", f"{count:,}") for p in entry["paragraphs"]]


def text_block_html(group, page_slug, count):
    """The text, facts and sources for a creator page, or "" when there is no text for this creator."""
    entry = get(group, page_slug)
    if not entry:
        return ""
    paras = "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs(entry, count))
    # only facts we actually know: a field with no answer is left out rather than shown as "Unknown"
    facts = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>" for k, v in entry["facts"]
                    if v and v.strip().lower() != "unknown")
    sources = "; ".join(f'<a href="{html.escape(u)}" target="_blank" rel="noopener noreferrer">{html.escape(label)}</a>'
                        for label, u in entry["sources"])
    return f"""
  <section class="creator-text">
    {paras}
    <dl class="creator-facts">{facts}</dl>
    <p class="creator-sources">Written by Formground from the creator's own site and named sources: {sources}. To correct or remove this text, write to <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>
  </section>"""


def style_tag(group, page_slug):
    return f"<style>{CREATOR_TEXT_CSS}</style>" if get(group, page_slug) else ""
