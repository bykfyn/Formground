// Share button on the static listing cards - the same behaviour as the Work page's own (search.js
// renderCard): native share sheet where there is one, otherwise copy "text + link"; a separate
// "share" event (never a click-through) goes to the same anonymous tracker.
document.addEventListener("click", function (e) {
  var btn = e.target.closest && e.target.closest(".results-grid .share-btn");
  if (!btn) return;
  e.preventDefault();
  e.stopPropagation();
  var card = btn.closest(".card");
  var product = card.getAttribute("data-product") || "";
  var brand = card.getAttribute("data-brand") || "";
  var text = product + " by " + brand + ". Discovered at Formground.com";
  var url = card.href;
  if (window.FGTrack) window.FGTrack.send("share", { brand: brand, product_name: product });
  if (navigator.share) {
    navigator.share({ title: product, text: text, url: url }).catch(function (err) {
      if (err.name !== "AbortError") console.error(err);
    });
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(text + "\n" + url).then(function () {
      btn.classList.add("copied");
      setTimeout(function () { btn.classList.remove("copied"); }, 1500);
    }).catch(function (err) { console.error(err); });
  }
});
