/* =========================================================================
   Theme (dark / light) — shared by the landing page and the studio.
   The stored choice is applied by an inline snippet in <head> before paint;
   this file only wires the toggle buttons and keeps them in sync.
   ========================================================================= */
(() => {
  "use strict";
  const KEY = "lnfp-theme";

  function current() {
    return document.documentElement.getAttribute("data-theme") === "light"
      ? "light" : "dark";
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem(KEY, theme); } catch { /* private mode */ }
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      const light = theme === "light";
      btn.setAttribute("aria-pressed", String(light));
      btn.setAttribute("title", light ? "الوضع الليلي" : "الوضع النهاري");
      const label = btn.querySelector("[data-theme-label]");
      if (label) label.textContent = light ? "ليلي" : "نهاري";
    });
  }

  window.LNFPTheme = { apply, current, toggle: () => apply(current() === "light" ? "dark" : "light") };

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-theme-toggle]");
    if (btn) { e.preventDefault(); window.LNFPTheme.toggle(); }
  });

  apply(current());
})();
