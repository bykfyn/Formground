// Type pages and maker pages (the listing template): the "See more" link and image sizing for cards added later.
//
// The page is complete without any of this: "See more" is a real link to the next numbered page, and the
// pager lists the pages, so crawlers, sharing and no-JavaScript visitors all work. With JavaScript the
// link instead fetches that next page and appends its cards to this grid (the same "see more results"
// behaviour as the Work page), then points itself at the page after that. Page numbers carry no meaning
// here (results are never ranked), so with JavaScript "See more" is the only visible way on: the numbered
// pager is hidden (CSS .has-load-more), and the address follows what has been loaded so a reload or a
// shared link lands where the visitor was.
(function () {
  var more = document.getElementById("see-more");
  var grid = document.querySelector("[data-listing-grid], .results-grid");   // type pages: .results-grid; maker pages: [data-listing-grid]

  // photos that are very narrow or very wide are shown whole, as on the Work page (search.js)
  document.addEventListener("load", function (e) {
    var img = e.target;
    if (img.tagName !== "IMG" || !img.closest || !img.closest(".card-image")) return;
    var ratio = img.naturalWidth / img.naturalHeight;
    if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
  }, true);

  if (grid) document.documentElement.classList.add("has-load-more");
  if (!more || !grid) return;
  var total = parseInt(more.getAttribute("data-total"), 10) || 0;
  var start = parseInt(more.getAttribute("data-start"), 10) || 0;   // cards before this page (page 3 starts at 120)
  var progress = document.getElementById("see-more-progress");
  var label = more.textContent;

  function showProgress(done) {
    if (!progress || !total) return;
    var shown = grid.children.length;
    var range = start ? (start + 1).toLocaleString() + "\u2013" + (start + shown).toLocaleString() : shown.toLocaleString();
    progress.textContent = (done && !start ? "Showing all " + total.toLocaleString()
                                           : "Showing " + range + " of " + total.toLocaleString());
  }
  showProgress();

  more.addEventListener("click", function (e) {
    var url = more.getAttribute("href");
    if (!url) return;
    e.preventDefault();
    more.setAttribute("aria-disabled", "true");
    more.textContent = "Loading…";
    fetch(url).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.text();
    }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, "text/html");
      doc.querySelectorAll("[data-listing-grid] .card, .results-grid .card").forEach(function (c) {
        grid.appendChild(document.importNode(c, true));
      });
      try { window.history.replaceState(null, "", url); } catch (e) { /* the address just stays put */ }
      var next = doc.getElementById("see-more");
      if (next && next.getAttribute("href")) {
        more.setAttribute("href", next.getAttribute("href"));
        more.textContent = label;
        more.removeAttribute("aria-disabled");
        showProgress();
      } else {
        more.remove();                 // that was the last page: leave only the closing count
        showProgress(true);
      }
    }).catch(function () {
      // leave the link working as a plain link to the next page
      more.textContent = label;
      more.removeAttribute("aria-disabled");
      window.location.href = url;
    });
  });
})();
