const API_BASE = window.FORMGROUND_API_BASE || "https://formground-git-182928637479.europe-west1.run.app";

// Read once per page load from the landing URL (e.g. ?utm_source=google&
// utm_medium=cpc&utm_campaign=test) - not stored anywhere (no cookie, no
// sessionStorage), just held in memory for this page view and attached
// to whatever search/discover/click happens during it, so an ad
// campaign's traffic can be attributed in aggregate. A UTM value is the
// same for every visitor who clicked the same ad - it identifies the
// campaign, not the person.
const urlParams = new URLSearchParams(window.location.search);
const UTM = {
  utm_source: urlParams.get("utm_source"),
  utm_medium: urlParams.get("utm_medium"),
  utm_campaign: urlParams.get("utm_campaign"),
};

// Bare "utm_source=x&utm_medium=y" with no leading separator - callers
// join it onto their own existing query string with "&" (search) or
// start a fresh one with "?" (discover).
function utmQueryString() {
  const params = new URLSearchParams();
  for (const key in UTM) {
    if (UTM[key]) params.set(key, UTM[key]);
  }
  return params.toString();
}

const form = document.getElementById("search-form");
const input = document.getElementById("query-input");
const statusEl = document.getElementById("status");
const metaEl = document.getElementById("results-meta");
const gridEl = document.getElementById("results-grid");

const CATEGORY_ICONS = {
  chair: "ti-armchair", stool: "ti-armchair", bench: "ti-armchair", seat: "ti-armchair",
  table: "ti-table", lamp: "ti-bulb", light: "ti-bulb", sconce: "ti-bulb",
  ceramic: "ti-vase", vase: "ti-vase", bowl: "ti-vase",
};

// A material that's just the singular of the category ("Ceramic" next
// to category "Ceramics") isn't a distinguishing per-item fact - it's
// the same word repeated on every card from that brand, reading as a
// fake category label sitting where no other card shows one.
function materialDuplicatesCategory(material, category) {
  if (!material || !category) return false;
  const norm = (s) => s.trim().toLowerCase().replace(/s$/, "");
  return norm(material) === norm(category);
}

function iconFor(category) {
  const c = (category || "").toLowerCase();
  for (const key in CATEGORY_ICONS) {
    if (c.includes(key)) return CATEGORY_ICONS[key];
  }
  return "ti-photo";
}

function iconMarkup(category) {
  return `<i class="ti ${iconFor(category)}" aria-hidden="true"></i>`;
}

function renderCard(r) {
  const a = document.createElement("a");
  a.className = "card" + (r.thin ? " thin" : "");
  // Falls back to the brand's homepage if check_links.py has flagged
  // this product page as a confirmed 404, so a card never leads to a
  // dead link between full scrapes.
  a.href = r.link_dead ? r.brand_url : r.product_url;
  a.target = "_blank";
  a.rel = "noopener noreferrer";

  // Anonymous, aggregate click signal only - no cookies, no
  // per-visitor identifier. sendBeacon fires this without blocking
  // the navigation to the maker's site (target="_blank" means it
  // doesn't even need to race a page unload, but sendBeacon is the
  // right tool either way - fire-and-forget, never throws).
  a.addEventListener("click", () => {
    const payload = JSON.stringify({
      query: input.value.trim() || null,
      brand: r.brand,
      product_name: r.product_name,
      ...UTM,
    });
    navigator.sendBeacon(`${API_BASE}/event`, new Blob([payload], { type: "application/json" }));
  });

  const imageDiv = document.createElement("div");
  imageDiv.className = "card-image";
  if (r.image_url) {
    // Set via property, not interpolated into an HTML string - this is
    // scraped data from an external site, not something to trust blindly.
    const img = document.createElement("img");
    img.src = r.image_url;
    img.alt = `${r.product_name} by ${r.brand}`;
    img.loading = "lazy";
    img.onerror = () => { imageDiv.innerHTML = iconMarkup(r.category); };
    // The square card-image box crops to fill by default (object-fit:
    // cover) - fine for a roughly square or moderately portrait/
    // landscape photo, but a real narrow product shot (confirmed on
    // several Magis chairs, e.g. Déjà-vu at ~221x446px) loses the top
    // and bottom of the actual product that way. Switches to "contain"
    // (whole image visible, letterboxed on the sides) only once the
    // real aspect ratio is known to be this extreme - most photos
    // never hit this and keep filling the box edge-to-edge as before.
    img.onload = () => {
      const ratio = img.naturalWidth / img.naturalHeight;
      if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
    };
    imageDiv.appendChild(img);
  } else {
    imageDiv.innerHTML = iconMarkup(r.category);
  }

  // Confirming the exact material the user searched for ("Available in
  // black") is a real, query-relevant fact worth the info-icon - a bare
  // variant count is not (some In Common With fixtures merge 1000+ raw
  // color/length SKUs into one card; "available in 1680 variants" tells
  // nobody anything useful). r.notes is kept as a general-purpose
  // per-item note field for any future real per-item fact, but nothing
  // populates it today.
  // Same "reads as a fake category label" problem as
  // materialDuplicatesCategory below applies here too - confirming
  // "Available in Ceramic" on a ceramics maker's card is redundant
  // with the brand/category context, unlike "Available in Black" on a
  // chair, which is genuinely informative. Filter per matched term
  // (matched_material can hold more than one, e.g. "black, oak") so a
  // genuinely useful term still shows even if another one is filtered.
  const matchedTerms = (r.matched_material || "")
    .split(", ")
    .filter((t) => t && !materialDuplicatesCategory(t, r.category));
  // Houses have no material/notes to show here - location + year is the
  // equivalent "one real fact worth a line" for a house the way
  // "Available in black" is for a chair (see _normalize_house in
  // query_engine.py for the aliased fields this reads).
  const houseDetail = r.type === "house"
    ? [r.location, r.year].filter(Boolean).join(" · ")
    : "";
  const noteText = matchedTerms.length
    ? `Available in ${matchedTerms.map((t) => t.charAt(0).toUpperCase() + t.slice(1)).join(", ")}`
    : (r.type === "house" ? "" : (r.notes || ""));

  const body = document.createElement("div");
  body.className = "card-body";
  body.innerHTML = `
    <div class="card-title-wrap"><p class="card-title"></p></div>
    <p class="card-brand"></p>
    ${noteText
      ? `<p class="card-note"><i class="ti ti-info-circle" aria-hidden="true"></i><span></span></p>`
      : `<p class="card-detail"></p>`}
  `;
  body.querySelector(".card-title").textContent = r.product_name;
  body.querySelector(".card-brand").textContent = r.brand;
  if (noteText) {
    body.querySelector(".card-note span").textContent = noteText;
  } else {
    // No raw material_options here even for a single entry - only a
    // search-confirmed match earns the "Available in X" note above.
    // An unconfirmed material is never shown plain, one or many.
    // Dimensions aren't shown either (2026-09-14) - this is a discovery
    // tool, not a spec sheet, and every card already links straight to
    // the maker's own product page where real dimensions and variants
    // live. r.notes is kept as a general-purpose per-item note field for
    // any future real per-item fact, but nothing populates it today.
    body.querySelector(".card-detail").textContent = houseDetail || r.notes || "";
  }

  // The "deep link" is the same destination the card itself already
  // goes to (the maker's own product page, or their homepage if
  // check_links.py flagged this one dead) - that's genuinely the
  // specific piece the sharer meant, not a Formground-hosted stand-in
  // (no per-product Formground pages exist, only per-brand ones).
  const shareBtn = document.createElement("button");
  shareBtn.className = "share-btn";
  shareBtn.type = "button";
  shareBtn.setAttribute("aria-label", "Share this piece");
  shareBtn.innerHTML = '<i class="ti ti-share-2" aria-hidden="true"></i>';
  shareBtn.addEventListener("click", (e) => {
    // Stop the click reaching the parent <a> - sharing shouldn't also
    // navigate away.
    e.preventDefault();
    e.stopPropagation();
    const shareUrl = a.href;
    const shareText = `Check out ${r.product_name} by ${r.brand} on Formground`;
    // Its own event, not the same "click" beacon a card navigation
    // fires (stopPropagation above means that one never fires here) -
    // sharing and clicking through are different actions worth telling
    // apart later.
    navigator.sendBeacon(
      `${API_BASE}/event`,
      new Blob([JSON.stringify({
        event_type: "share",
        query: input.value.trim() || null,
        brand: r.brand,
        product_name: r.product_name,
        ...UTM,
      })], { type: "application/json" }),
    );
    if (navigator.share) {
      // Native share sheet (mobile mostly) - a real OS-level standard,
      // not something to build a custom picker for. AbortError just
      // means the user closed the sheet without picking anything -
      // not a real failure, so it's swallowed rather than surfaced.
      navigator.share({ title: r.product_name, text: shareText, url: shareUrl })
        .catch((err) => { if (err.name !== "AbortError") console.error(err); });
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(shareUrl).then(() => {
        shareBtn.classList.add("copied");
        setTimeout(() => shareBtn.classList.remove("copied"), 1500);
      }).catch((err) => console.error(err));
    }
  });
  // Appended to imageDiv, not body - the share button overlays the
  // photo's own bottom-right corner now that the card has no enclosing
  // surface for it to sit inside (2026-09-20, matches Creators/the
  // homepage's photo+plain-caption pattern - see project memory).
  imageDiv.appendChild(shareBtn);

  a.appendChild(imageDiv);
  a.appendChild(body);
  return a;
}

function renderResults(results, metaText, emptyText, trimToFullRows) {
  gridEl.innerHTML = "";
  statusEl.style.display = "none";

  if (results.length === 0) {
    statusEl.className = "";
    statusEl.style.display = "block";
    statusEl.textContent = emptyText;
    metaEl.style.display = "none";
    return;
  }

  results.forEach(r => gridEl.appendChild(renderCard(r)));

  // Discover's grid is a real count of real objects, but an odd-length
  // trailing row (fuller rows above it, then 2 cards alone on the last
  // line) looks unfinished in a way a search result count doesn't - a
  // search's count is itself informative ("13 results"), so it's never
  // trimmed. The grid's own column count isn't fixed in CSS (auto-fit
  // reflows by viewport width), so this reads it back from the
  // rendered layout rather than guessing - it's the only way to
  // actually guarantee a full last row at any window size.
  if (trimToFullRows) {
    const columns = getComputedStyle(gridEl).gridTemplateColumns.trim().split(/\s+/).length;
    const keep = Math.floor(results.length / columns) * columns || results.length;
    while (gridEl.children.length > keep) {
      gridEl.removeChild(gridEl.lastElementChild);
    }
    results = results.slice(0, keep);
  }

  metaEl.textContent = metaText(results.length);
  metaEl.style.display = "block";
}

async function runSearch(query) {
  gridEl.innerHTML = "";
  metaEl.style.display = "none";
  statusEl.className = "";
  statusEl.style.display = "block";
  statusEl.textContent = "Searching…";

  try {
    const utmSuffix = utmQueryString();
    const resp = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}${utmSuffix ? `&${utmSuffix}` : ""}`);
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
    const data = await resp.json();
    renderResults(
      data.results || [],
      (n) => `${n} result${n === 1 ? "" : "s"}, real makers, no rankings`,
      "No matches yet - try describing it a different way."
    );
  } catch (err) {
    statusEl.className = "error";
    statusEl.style.display = "block";
    statusEl.textContent = "Couldn't reach Formground's search right now - please try again shortly.";
    console.error(err);
  }
}

async function runDiscover() {
  gridEl.innerHTML = "";
  metaEl.style.display = "none";
  statusEl.className = "";
  statusEl.style.display = "block";
  statusEl.textContent = "Shuffling…";

  try {
    const utmSuffix = utmQueryString();
    const resp = await fetch(`${API_BASE}/discover${utmSuffix ? `?${utmSuffix}` : ""}`);
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
    const data = await resp.json();
    renderResults(
      data.results || [],
      (n) => `${n} real objects, picked at random across every maker`,
      "Nothing to discover yet.",
      true
    );
  } catch (err) {
    statusEl.className = "error";
    statusEl.style.display = "block";
    statusEl.textContent = "Couldn't reach Formground right now - please try again shortly.";
    console.error(err);
  }
}

// Always navigates to /work.html, even when already there - a refined
// or shuffled query changes what's on screen, and the URL has to change
// with it so the address bar always matches what's displayed and stays
// shareable. Typing "random" is treated the same as leaving the box
// empty - both trigger the same "Surprise me" discovery. (This page was
// itself /search.html until 2026-09-19 - "Work" was always meant to be
// the real browsing/results surface, so it took over this URL rather
// than staying a separate, more limited chip-browsing page - see
// project memory.)
function submitQuery(q) {
  const trimmed = (q || "").trim();
  const params = new URLSearchParams();
  if (trimmed && trimmed.toLowerCase() !== "random") {
    params.set("q", trimmed);
  } else {
    params.set("discover", "1");
  }
  window.location.href = `/work.html?${params.toString()}`;
}

if (form) {
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    submitQuery(input.value.trim());
  });

  // Explicit fallback: don't rely solely on native "Enter submits the
  // form" behavior for a single-input form - some environments don't
  // reliably dispatch that.
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submitQuery(input.value.trim());
    }
  });
}

// Blank field: full random discovery. A typed query: re-run that same
// search instead - results are capped per brand and randomly selected
// each time (see cap_per_brand), so a search with more matches than
// shown surfaces a fresh set rather than the same one every time.
const discoverChip = document.getElementById("discover-chip");
if (discoverChip) {
  discoverChip.addEventListener("click", () => {
    submitQuery(input.value.trim());
  });
}

// Only present on work.html - the homepage has no results grid, so
// this block simply never runs there. Reads the query straight from the
// URL on load and auto-runs it, so a shared/bookmarked link reproduces
// exactly what was shown when it was shared.
if (gridEl) {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");

  if (q && q.trim().toLowerCase() !== "random") {
    input.value = q;
    runSearch(q);
  } else {
    input.value = "";
    runDiscover();
  }
}
