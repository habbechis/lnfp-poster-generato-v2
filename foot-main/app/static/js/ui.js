/* =========================================================================
   Shell chrome: the sidebar drawer and its hamburger.

   The sidebar is permanent on desktop (CSS grid column) and becomes an
   off-canvas drawer below the breakpoint, where the hamburger appears.
   ========================================================================= */
(() => {
  "use strict";
  const MOBILE = "(max-width: 1024px)";
  const sidebar = document.getElementById("sidebar");
  const scrim = document.getElementById("sidebarScrim");
  const toggle = document.getElementById("menuToggle");
  const closeBtn = document.getElementById("menuClose");
  if (!sidebar || !toggle) return;

  const isMobile = () => window.matchMedia(MOBILE).matches;

  function setOpen(open) {
    document.body.classList.toggle("is-drawer-open", open);
    sidebar.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    if (scrim) scrim.hidden = !open;
  }

  toggle.addEventListener("click", () => setOpen(!sidebar.classList.contains("is-open")));
  if (closeBtn) closeBtn.addEventListener("click", () => setOpen(false));
  if (scrim) scrim.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && sidebar.classList.contains("is-open")) setOpen(false);
  });
  // Following a link inside the drawer should close it on mobile.
  sidebar.addEventListener("click", (e) => {
    if (isMobile() && e.target.closest("a, .comp-chip")) setOpen(false);
  });
  // Leaving mobile width must not strand the drawer state.
  window.matchMedia(MOBILE).addEventListener("change", () => setOpen(false));

  window.LNFPShell = { closeDrawer: () => setOpen(false) };
})();
