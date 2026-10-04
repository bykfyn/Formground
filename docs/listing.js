// Type pages (the listing template): the "See more" link and image sizing for cards added later.
//
// The page is complete without any of this: "See more" is a real link to the next numbered page, and the
// pager lists the pages, so crawlers, sharing and no-JavaScript visitors all work. With JavaScript the
// link instead fetches that next page and appends its cards to this grid (the same "see more results"
// behaviour as the Work page), then points itself at the page after that.
(function () {
  var more = document.getElementById("see-more");
  var grid = document.querySelector(".results-grid");

  // photos that are very narrow or very wide are shown whole, as on the Work page (search.js)
  document.addEventListener("load", function (e) {
    var img = e.target;
    if (img.tagName !== "IMG" || !img.closest || !img.closest(".card-image")) return;
    var ratio = img.naturalWidth / img.naturalHeight;
    if (ratio < 0.55 || ratio > 1.8) img.classList.add("contain-fit");
  }, true);

  if (!more || !grid) return;
  var total = parseInt(more.getAttribute("data-total"), 10) || 0;
  var progress = document.getElementById("see-more-progress");
  var label = more.textContent;

  function showProgress() {
    if (progress && total) progress.textContent = "Showing " + grid.children.length.toLocaleString() + " of " + total.toLocaleString();
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
      doc.querySelectorAll(".results-grid .card").forEach(function (c) {
        grid.appendChild(document.importNode(c, true));
      });
      var next = doc.getElementById("see-more");
      if (next && next.getAttribute("href")) {
        more.setAttribute("href", next.getAttribute("href"));
        more.textContent = label;
        more.removeAttribute("aria-disabled");
        showProgress();
      } else {
        more.parentElement.remove();   // that was the last page
      }
    }).catch(function () {
      // leave the link working as a plain link to the next page
      more.textContent = label;
      more.removeAttribute("aria-disabled");
      window.location.href = url;
    });
  });
})();
