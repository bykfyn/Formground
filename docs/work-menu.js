// "Browse by type" menu: one category panel open at a time; Escape closes it.
// Without JavaScript every panel is shown (see the <noscript> rule on the page).
(function () {
  var menu = document.querySelector(".work-menu");
  if (!menu) return;
  var buttons = menu.querySelectorAll(".work-menu-cat");
  function setOpen(button, open) {
    button.setAttribute("aria-expanded", open ? "true" : "false");
    var panel = document.getElementById(button.getAttribute("aria-controls"));
    if (panel) panel.hidden = !open;
  }
  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      var willOpen = b.getAttribute("aria-expanded") !== "true";
      buttons.forEach(function (o) { setOpen(o, false); });
      setOpen(b, willOpen);
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") buttons.forEach(function (o) { setOpen(o, false); });
  });
})();
