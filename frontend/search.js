const API_BASE = window.FORMGROUND_API_BASE || "https://formground-git-182928637479.europe-west1.run.app";

// Read once per page load from the landing URL (e.g. ?utm_source=google&
// utm_medium=cpc&utm_campaign=test) - not stored anywhere (no cookie, no
// sessionStorage), just held in memory for this page view and attached
// to whatever search/discover/click happens during it, so an ad
// campaign's traffic can be attributed in aggregate. A UTM value is the
// same for every visitor who clicked the same ad - it identifies the
// campaign, not the person.
const urlParams = new URLSearchParams(window.location.search);
// Since 2026-10-02 the campaign (and the visit's landing page) comes from
// fg-track.js, which carries both across pages of the same browser tab via
// sessionStorage - so an ad's attribution survives navigating past the
// landing page. Falls back to this page's own URL if that file did not load.
const TRACK = window.FGTrack || null;
const UTM = TRACK ? TRACK.ctx.utm : {
  utm_source: urlParams.get("utm_source"),
  utm_medium: urlParams.get("utm_medium"),
  utm_campaign: urlParams.get("utm_campaign"),
};

// The id /search or /discover returned for the results now on screen
// (random per search, not per person) - echoed on a click so it joins to
// the exact search that produced it.
let currentSearchId = null;

// page_path / landing_page (+ search_id) for every event this file sends.
function trackExtra() {
  const extra = TRACK ? TRACK.extra() : { page_path: window.location.pathname };
  if (currentSearchId) extra.search_id = currentSearchId;
  return extra;
}

// Never report from a local preview.
const TRACKING_ON = window.FG_TRACK_FORCE || !/^(localhost|127\.0\.0\.1|\[::1\]|)$/.test(window.location.hostname);
function beacon(payload) {
  if (!TRACKING_ON) return;
  navigator.sendBeacon(`${API_BASE}/event`, new Blob([JSON.stringify(payload)], { type: "application/json" }));
}

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

// Card-sized copy of a maker's photo (2026-10-04). Makers' servers mostly send
// the full-size original - a 1.4MB photo for a ~190px card - so each image
// asks its host for the width it will actually be shown at. Same rules, and
// the reasons, as scraper/image_sizes.py (keep the two in step); a host with
// no verified resize rule is returned untouched.
function sizedImage(url, width) {
  try {
    const u = new URL(url);
    const h = u.hostname.toLowerCase();
    if (h === "cdn.shopify.com") {
      u.searchParams.set("width", width);
    } else if (h === "images.squarespace-cdn.com" || h === "static1.squarespace.com") {
      u.searchParams.set("format", width + "w");
    } else if (h === "images.fogia.com") {
      u.searchParams.set("w", width);
    } else if (h === "www.datocms-assets.com") {
      u.searchParams.delete("h");
      u.searchParams.set("w", width);
      u.searchParams.set("auto", "format");
    } else if (h === "images.ctfassets.net") {
      u.searchParams.set("w", width);
      u.searchParams.set("fm", "webp");
      u.searchParams.set("q", 80);
    } else if (h === "www.hay.com" || h === "cdn.thorcommerce.io") {
      u.searchParams.set("w", width);
    } else if (h === "cdn.sanity.io") {
      u.searchParams.set("w", width);
      u.searchParams.set("auto", "format");
    } else if (h === "static.wixstatic.com" && u.pathname.indexOf("/media/") === 0) {
      const base = u.origin + u.pathname.split("/v1/")[0];
      const ext = base.split(".").pop().toLowerCase();
      if (["jpg", "jpeg", "png", "webp", "gif"].indexOf(ext) === -1) return url;
      return base + "/v1/fit/w_" + width + ",h_" + width + ",q_80/file." + ext;
    } else {
      return url;
    }
    return u.toString();
  } catch (e) {
    return url;
  }
}

// Only present on work.html - "independent" or "established" (the
// Independent/Established Makers chips), read from the URL the same
// way UTM is, so a shared/bookmarked link reproduces the exact same
// filtered view. Never touched by the search/discover text itself -
// this is an explicit chip choice, not something the query means (see
// backend/query_engine.py's own tier docstring for why it's threaded
// through separately from _resolve_intent).
const TIER = urlParams.get("tier");

// Re-navigates to the same q/discover state currently on screen, with
// the tier param toggled - clicking the already-active chip clears it
// back to both tiers. A full navigation, not an in-place re-fetch,
// matching how "Surprise me" already works on this page (submitQuery
// below also just sets window.location.href) - reuses the exact same
// URL-read-on-load pipeline with no separate re-render path to keep in
// sync.
function applyTierFilter(tier) {
  const params = new URLSearchParams(window.location.search);
  if (tier === TIER) {
    params.delete("tier");
  } else {
    params.set("tier", tier);
  }
  window.location.href = `/work.html?${params.toString()}`;
}

const form = document.getElementById("search-form");
const input = document.getElementById("query-input");
const statusEl = document.getElementById("status");
const metaEl = document.getElementById("results-meta");
const gridEl = document.getElementById("results-grid");
const loadMoreRow = document.getElementById("load-more-row");
const loadMoreBtn = document.getElementById("load-more-btn");
const loadMoreProgress = document.getElementById("load-more-progress");

// Number of leftover cards revealed per "See more results" click - a UI
// pacing choice, independent of the fairness math that orders the pool
// (see round_robin_order() in query_engine.py). Mocked up and measured
// against a real 1,418-match "chair" search before picking this number -
// see project memory, [[search_load_more_design]].
const LOAD_MORE_CHUNK_SIZE = 180;

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
    beacon({
      event_type: "click",
      query: input.value.trim() || null,
      brand: r.brand,
      product_name: r.product_name,
      surface: "work",
      position: a.parentNode ? Array.prototype.indexOf.call(a.parentNode.children, a) + 1 : null,
      target_url: a.href,
      ...trackExtra(),
      ...UTM,
    });
  });

  const imageDiv = document.createElement("div");
  imageDiv.className = "card-image";
  if (r.image_url) {
    // Set via property, not interpolated into an HTML string - this is
    // scraped data from an external site, not something to trust blindly.
    const img = document.createElement("img");
    img.src = sizedImage(r.image_url, 500);
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
    const shareText = `${r.product_name} by ${r.brand}. Discovered at Formground.com`;
    // Its own event, not the same "click" beacon a card navigation
    // fires (stopPropagation above means that one never fires here) -
    // sharing and clicking through are different actions worth telling
    // apart later.
    beacon({
      event_type: "share",
      query: input.value.trim() || null,
      brand: r.brand,
      product_name: r.product_name,
      ...trackExtra(),
      ...UTM,
    });
    if (navigator.share) {
      // Native share sheet (mobile mostly) - a real OS-level standard,
      // not something to build a custom picker for. AbortError just
      // means the user closed the sheet without picking anything -
      // not a real failure, so it's swallowed rather than surfaced.
      navigator.share({ title: r.product_name, text: shareText, url: shareUrl })
        .catch((err) => { if (err.name !== "AbortError") console.error(err); });
    } else if (navigator.clipboard) {
      // Desktop copy-link path had no attribution text, unlike the
      // mobile share-sheet branch above which already passes shareText
      // - now both carry the same "Check out X by Y on Formground"
      // line, just plain text above the link since a clipboard paste
      // has no separate title/body/url fields to fill.
      navigator.clipboard.writeText(`${shareText}\n${shareUrl}`).then(() => {
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

// Removes a trailing partial row from the results grid (fewer cards
// than the grid's own column count) and returns the result objects it
// corresponded to, so the caller can carry them into the *next* reveal
// instead of ever leaving a half-empty last row on screen. Only valid
// right after appending `renderedItems` with nothing else queued
// behind them - relies on gridEl.children still being in the same
// order the array was built in. The grid's own column count isn't
// fixed in CSS (auto-fit reflows by viewport width), so this reads it
// back from the rendered layout rather than guessing.
function trimTrailingPartialRow(renderedItems) {
  const columns = getComputedStyle(gridEl).gridTemplateColumns.trim().split(/\s+/).length;
  const total = gridEl.children.length;
  const keep = Math.floor(total / columns) * columns || total;
  const carryCount = total - keep;
  if (carryCount === 0) return [];
  for (let i = 0; i < carryCount; i++) {
    gridEl.removeChild(gridEl.lastElementChild);
  }
  return renderedItems.slice(renderedItems.length - carryCount);
}

function renderResults(results, metaText, emptyText, trimToFullRows, totalOverride) {
  gridEl.innerHTML = "";
  statusEl.style.display = "none";
  hideLoadMore();

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

  // totalOverride is the real pre-cap match count (search only, from
  // /search's total_matches) - falls back to the rendered count itself
  // for Discover, which has no such hidden total to report.
  metaEl.textContent = metaText(totalOverride ?? results.length);
  metaEl.style.display = "block";
}

// --- "See more results" (search only - see project memory,
// [[search_load_more_design]] for why a per-brand fairness cap hides
// most real matches by default, and why this reveals the rest instead
// of silently dropping them) ---
let moreState = null;

function hideLoadMore() {
  loadMoreRow.hidden = true;
  loadMoreBtn.disabled = false;
  loadMoreBtn.textContent = "See more results";
  moreState = null;
}

function updateLoadMoreProgress() {
  const { shown, total, totalBrands } = moreState;
  loadMoreProgress.textContent = `Showing ${shown.toLocaleString()} of ${total.toLocaleString()}, from every one of ${totalBrands} brand${totalBrands === 1 ? "" : "s"}`;
}

// Reveals up to `count` items from the pool, folding in whatever the
// *previous* reveal trimmed off its own trailing row (moreState.carryOver)
// so a carried-over remainder appears first rather than being held
// forever. Trims its own new trailing row the same way, unless the
// pool is now exhausted - at that point nothing more is ever coming to
// complete the row, so everything left gets shown, ragged edge and all,
// rather than silently withholding real matches.
function revealFromPool(count) {
  const carriedIn = moreState.carryOver;
  moreState.carryOver = [];
  const fromPool = moreState.pool.slice(moreState.poolIndex, moreState.poolIndex + Math.max(0, count - carriedIn.length));
  const chunk = carriedIn.concat(fromPool);
  moreState.poolIndex += fromPool.length;

  chunk.forEach(r => gridEl.appendChild(renderCard(r)));
  const exhausted = moreState.poolIndex >= moreState.pool.length;

  if (exhausted) {
    moreState.shown += chunk.length;
    loadMoreBtn.remove();
    loadMoreProgress.textContent = `That's every result — ${moreState.total.toLocaleString()} of ${moreState.total.toLocaleString()}.`;
    return;
  }

  const carried = trimTrailingPartialRow(chunk);
  moreState.shown += chunk.length - carried.length;
  moreState.carryOver = carried;
  updateLoadMoreProgress();
}

// Shows the "See more results" row only when there's real, undisclosed
// supply behind the fairness cap - a small query where nothing was
// hidden (total_matches === results shown) gets no button at all, and
// `carryOver` (the initial batch's own trailing partial row, if any -
// see trimTrailingPartialRow) is only ever non-empty in that same case,
// since a fully-shown batch has nothing left to defer.
// Also guards against an old backend response that predates these
// fields (e.g. this frontend deployed slightly ahead of the backend,
// or a local test pointed at the still-live production API) - without
// this check, a missing total_matches used to throw partway through
// setup and take the rest of the search page down with it.
function setupLoadMore(query, intent, shownResults, carryOver, totalMatches, totalBrands) {
  if (typeof totalMatches !== "number" || typeof totalBrands !== "number" || !intent) {
    hideLoadMore();
    return;
  }
  if (totalMatches <= shownResults.length) {
    hideLoadMore();
    return;
  }
  moreState = {
    query, intent,
    shownIds: shownResults.map(r => r.id),
    pool: null,
    pendingCarry: carryOver,
    poolIndex: 0,
    carryOver: [],
    shown: shownResults.length - carryOver.length,
    total: totalMatches,
    totalBrands,
  };
  loadMoreRow.hidden = false;
  loadMoreBtn.disabled = false;
  loadMoreBtn.textContent = "See more results";
  updateLoadMoreProgress();
}

async function handleLoadMoreClick() {
  if (!moreState) return;

  // Pool not fetched yet - one /search/more call gets back every
  // remaining match in a single response, already round-robin ordered
  // (see query_engine.round_robin_order); every click after this one
  // just reveals more of that same in-memory list, no further network
  // calls needed. Whatever the initial batch's own trailing row
  // deferred (pendingCarry) gets folded in right here, so it appears
  // as part of this same first "load more" click instead of a
  // separate, tiny click of its own.
  if (moreState.pool === null) {
    loadMoreBtn.disabled = true;
    loadMoreBtn.textContent = "Loading…";
    try {
      const params = new URLSearchParams({
        q: moreState.query,
        intent: JSON.stringify(moreState.intent),
        exclude: moreState.shownIds.join(","),
      });
      if (currentSearchId) params.set("search_id", currentSearchId);
      const resp = await fetch(`${API_BASE}/search/more?${params.toString()}`);
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
      const data = await resp.json();
      moreState.pool = moreState.pendingCarry.concat(data.results || []);
    } catch (err) {
      console.error(err);
      loadMoreBtn.disabled = false;
      loadMoreBtn.textContent = "Couldn't load more - try again";
      return;
    }
    loadMoreBtn.disabled = false;
    loadMoreBtn.textContent = "See more results";
  }

  revealFromPool(LOAD_MORE_CHUNK_SIZE);
}

// Only present on work.html - unguarded, this threw on every other page
// that loads search.js (including the homepage), halting the rest of
// the script before it ever reached the search-form submit handler
// below - the real cause of a live, critical bug: the homepage's search
// box silently did nothing on Enter/submit. Confirmed live 2026-09-29.
if (loadMoreBtn) {
  loadMoreBtn.addEventListener("click", handleLoadMoreClick);
}

// The Work page always loads results (a search, or "Surprise me" with no query).
// Until they arrive the grid is empty, so the footer sat right under the search
// box and was then pushed far down - the page's only layout shift (CLS 0.12 on
// a phone, measured 2026-10-04). work.html starts <main> as .results-loading,
// which keeps the footer invisible; this reveals it once the results (or an
// error message) are in place, so nothing visible moves.
function finishLoading() {
  const m = document.querySelector("main.results-loading");
  if (m) m.classList.remove("results-loading");
}

async function runSearch(query) {
  gridEl.innerHTML = "";
  metaEl.style.display = "none";
  hideLoadMore();
  statusEl.className = "";
  statusEl.style.display = "block";
  statusEl.textContent = "Searching…";

  try {
    const utmSuffix = utmQueryString();
    const tierSuffix = TIER ? `&tier=${encodeURIComponent(TIER)}` : "";
    const where = `&page_path=${encodeURIComponent(window.location.pathname)}` +
      (TRACK ? `&landing_page=${encodeURIComponent(TRACK.ctx.landing_page)}` : "");
    const resp = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}${utmSuffix ? `&${utmSuffix}` : ""}${tierSuffix}${where}`);
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
    const data = await resp.json();
    currentSearchId = data.search_id || null;
    const results = data.results || [];
    renderResults(
      results,
      // Copy-paste bug fixed 2026-09-29 (found while investigating a
      // handoff report that search "doesn't work"): this used to reuse
      // runDiscover's "random results" phrasing verbatim even for a
      // real, specific query - the search itself was always working
      // (confirmed live: real filtered results, real total_matches from
      // the API), but the label made every result look like unfiltered
      // Discover output, indistinguishable from a broken search at a
      // glance. metaEl uses textContent, not innerHTML, so query needs
      // no HTML-escaping here.
      (n) => `${n.toLocaleString()} result${n === 1 ? "" : "s"} for "${query}", no rankings, not paid for`,
      "No matches yet - try describing it a different way.",
      false,
      data.total_matches
    );
    if (results.length > 0) {
      // Only worth trimming the initial batch's own trailing row when
      // there's real hidden content to carry it into - a fully-shown
      // batch (nothing left behind the fairness cap) has nowhere for a
      // deferred card to go, so it's left exactly as it always has been.
      const hasHidden = typeof data.total_matches === "number" && data.total_matches > results.length;
      const carryOver = hasHidden ? trimTrailingPartialRow(results) : [];
      setupLoadMore(query, data.intent, results, carryOver, data.total_matches, data.total_brands);
    }
  } catch (err) {
    statusEl.className = "error";
    statusEl.style.display = "block";
    statusEl.textContent = "Couldn't reach Formground's search right now - please try again shortly.";
    console.error(err);
  } finally {
    finishLoading();
  }
}

async function runDiscover() {
  gridEl.innerHTML = "";
  metaEl.style.display = "none";
  hideLoadMore();
  statusEl.className = "";
  statusEl.style.display = "block";
  statusEl.textContent = "Shuffling…";

  try {
    const utmSuffix = utmQueryString();
    const tierSuffix = TIER ? `tier=${encodeURIComponent(TIER)}` : "";
    const where = `page_path=${encodeURIComponent(window.location.pathname)}` +
      (TRACK ? `&landing_page=${encodeURIComponent(TRACK.ctx.landing_page)}` : "");
    const discoverQuery = [utmSuffix, tierSuffix, where].filter(Boolean).join("&");
    const resp = await fetch(`${API_BASE}/discover${discoverQuery ? `?${discoverQuery}` : ""}`);
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
    const data = await resp.json();
    currentSearchId = data.search_id || null;
    renderResults(
      data.results || [],
      (n) => `${n} random pieces, no rankings, no paid results`,
      "Nothing to discover yet.",
      true
    );
  } catch (err) {
    statusEl.className = "error";
    statusEl.style.display = "block";
    statusEl.textContent = "Couldn't reach Formground right now - please try again shortly.";
    console.error(err);
  } finally {
    finishLoading();
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

// Only present on work.html - highlights whichever tier the URL
// already carries (a shared/bookmarked filtered link lands with the
// right chip already active) and wires each chip to applyTierFilter().
document.querySelectorAll(".filter-chip[data-tier]").forEach((btn) => {
  if (btn.dataset.tier === TIER) btn.classList.add("active");
  btn.addEventListener("click", () => applyTierFilter(btn.dataset.tier));
});

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
    // The page opened on a random selection: mark "Surprise me" as the active view (dark pill) so the visitor
    // understands what they are looking at and that the same button reshuffles it.
    if (discoverChip) {
      discoverChip.classList.add("is-active");
      discoverChip.setAttribute("aria-pressed", "true");
      discoverChip.title = "A random selection - click to reshuffle";
    }
    runDiscover();
  }
}

// Only present on the homepage's category tiles (.cat-tile figures with
// a "Visit site" link straight to that tile's example maker/architect
// page) - a no-op everywhere else. Previously fired no event at all,
// unlike every other click-through to a maker's site on the results
// page (2026-09-24).
document.querySelectorAll(".visit-source").forEach((link) => {
  link.addEventListener("click", () => {
    const tile = link.closest(".cat-tile");
    beacon({
      event_type: "click",
      brand: tile ? tile.querySelector(".product-maker")?.textContent.trim() : null,
      product_name: tile ? tile.querySelector(".product-name")?.textContent.trim() : null,
      target_url: link.href,
      ...trackExtra(),
      ...UTM,
    });
  });
});

// Which homepage category tile (House/Furniture/Lighting/Objects) got
// clicked, before it navigates to work.html?q=... - reuses the "query"
// field to hold the category name (e.g. "house"), the same real
// signal a typed search would put there, so this needs no new BigQuery
// column. A no-op everywhere .cat-link doesn't exist (2026-09-24).
document.querySelectorAll(".cat-link").forEach((link) => {
  link.addEventListener("click", () => {
    const category = new URLSearchParams(link.href.split("?")[1]).get("q");
    beacon({
      event_type: "category_click",
      query: category,
      ...trackExtra(),
      ...UTM,
    });
  });
});
