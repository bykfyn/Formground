/*
 * Formground anonymous event tracking - the one shared client for page
 * views and click-throughs. Loaded on every page (generated pages inject it
 * via CARD_CLICK_TRACKING_JS; index/work/marketplace/for-creators load it
 * directly). What is logged and why: backend/analytics.py.
 *
 * Privacy: no cookie, no user id, no session id. The only thing kept in
 * sessionStorage (per browser TAB, cleared when it closes) is the campaign
 * UTM values and the path of the first page of the visit - both identical
 * for everyone who arrives the same way, so they describe a campaign and a
 * landing page, never a person. Nothing is sent from localhost.
 *
 * Exposes window.FGTrack = { ctx, extra(), send(type, fields) } so
 * search.js attaches the same landing page / campaign to its own events.
 */
(function () {
  "use strict";
  var API_BASE = window.FORMGROUND_API_BASE || "https://formground-git-182928637479.europe-west1.run.app";
  var host = window.location.hostname;
  // window.FG_TRACK_FORCE exists only so the wiring can be verified from a local preview.
  var enabled = window.FG_TRACK_FORCE || !(host === "" || host === "localhost" || host === "127.0.0.1" || host === "[::1]" || /\.localhost$/.test(host));

  function load(key) {
    try { return window.sessionStorage.getItem(key); } catch (e) { return null; }
  }
  function store(key, value) {
    try { window.sessionStorage.setItem(key, value); } catch (e) { /* storage blocked: fall back to this page only */ }
  }

  // --- visit context: campaign + landing page, carried across pages of the tab ---
  var params = new URLSearchParams(window.location.search);
  var urlUtm = {
    utm_source: params.get("utm_source"),
    utm_medium: params.get("utm_medium"),
    utm_campaign: params.get("utm_campaign"),
  };
  var hasUtm = !!(urlUtm.utm_source || urlUtm.utm_medium || urlUtm.utm_campaign);
  var landing = load("fg_landing");
  var utm = null;
  try { utm = JSON.parse(load("fg_utm") || "null"); } catch (e) { utm = null; }
  if (hasUtm) {
    // Arriving from an ad: THIS page is the landing page for that campaign.
    landing = window.location.pathname;
    utm = urlUtm;
    store("fg_landing", landing);
    store("fg_utm", JSON.stringify(utm));
  } else if (!landing) {
    landing = window.location.pathname;
    store("fg_landing", landing);
  }
  var ctx = {
    utm: utm || { utm_source: null, utm_medium: null, utm_campaign: null },
    landing_page: landing,
    page_path: window.location.pathname,
  };

  function extra() {
    return { page_path: ctx.page_path, landing_page: ctx.landing_page };
  }

  function send(type, fields) {
    if (!enabled || !navigator.sendBeacon) return;
    var payload = JSON.stringify(Object.assign({ event_type: type }, extra(), ctx.utm, fields || {}));
    navigator.sendBeacon(API_BASE + "/event", new Blob([payload], { type: "application/json" }));
  }

  window.FGTrack = { ctx: ctx, extra: extra, send: send };

  function textOf(el) {
    return el ? el.textContent.trim() : null;
  }

  var pageBrandEl = document.querySelector(".maker-header .maker-name");
  var pageBrand = pageBrandEl ? pageBrandEl.textContent.trim() : null;

  function referrerHost() {
    try {
      if (!document.referrer) return null;
      var h = new URL(document.referrer).hostname;
      return h && h !== host ? h : null;  // internal navigation is not a referrer
    } catch (e) { return null; }
  }

  function pageview() {
    var brands = [];
    document.querySelectorAll(".card-brand").forEach(function (el) {
      var b = textOf(el);
      if (b && brands.indexOf(b) === -1) brands.push(b);
    });
    var fields = { referrer_host: referrerHost() };
    if (pageBrand) fields.brand = pageBrand;          // a maker's own page
    if (brands.length) fields.result_brands = brands.slice(0, 150);  // makers shown here
    send("pageview", fields);
  }

  // Click-throughs on server-rendered cards. Pages that load search.js
  // (home, work) build their cards dynamically and report their own clicks.
  // One delegated listener (not one per card) so cards added later - the type
  // pages' "See more" appends the next batch - are tracked exactly like the first.
  function bindClicks() {
    if (document.querySelector('script[src*="search.js"]')) return;
    document.addEventListener("click", function (ev) {
      var el = ev.target.closest && ev.target.closest(".maker-card, .card, .brand-site-link");
      if (!el) return;
      if (!el.hostname || el.hostname === window.location.hostname) return;
      if (ev.target.closest(".share-btn")) return;  // sharing is its own event (share.js)

      var brand, productName;
      if (el.classList.contains("card")) {
        productName = textOf(el.querySelector(".card-title"));
        brand = textOf(el.querySelector(".card-brand")) || pageBrand;
      } else if (el.classList.contains("brand-site-link")) {
        brand = pageBrand;
        productName = null;
      } else if (pageBrand) {
        brand = pageBrand;
        productName = textOf(el.querySelector(".maker-name"));
      } else {
        brand = textOf(el.querySelector(".maker-name"));
        productName = textOf(el.querySelector(".maker-categories"));
      }

      var fields = { brand: brand, product_name: productName, target_url: el.href };
      var index = Array.prototype.indexOf.call(document.querySelectorAll(".card"), el);
      if (index !== -1) fields.position = index + 1;   // rank within this page's grid
      send("click", fields);
    });
  }

  function init() {
    pageview();
    bindClicks();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
