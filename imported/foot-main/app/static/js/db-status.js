/* Database heartbeat.
 *
 * Polls /api/db-status and reflects the result on two optional elements:
 *   #dbStatus  — the small dot + label in the studio sidebar
 *   #dbBanner  — the wider pill on the admin panel
 * Either may be absent (the script no-ops for whatever is missing). The dot
 * turns green when a remote Firebase backend answers, red otherwise. Text is
 * Arabic; i18n.js translates it to French when that language is active.
 */
(function () {
  "use strict";

  var dot = document.getElementById("dbStatus");
  var banner = document.getElementById("dbBanner");
  if (!dot && !banner) return;

  var TEXT = {
    checking: "جارٍ التحقّق…",
    connected: "قاعدة البيانات متّصلة — العمليات متاحة",
    offline: "قاعدة البيانات غير متّصلة — تخزين محلّي مؤقّت",
  };

  function paint(state) {
    if (dot) {
      dot.setAttribute("data-state", state);
      var t = dot.querySelector(".db-status__text");
      if (t) t.textContent = TEXT[state];
    }
    if (banner) {
      banner.setAttribute("data-state", state);
      var b = banner.querySelector(".db-banner__text");
      if (b) b.textContent = state === "checking"
        ? "جارٍ التحقّق من قاعدة البيانات…" : TEXT[state];
    }
    // i18n.js watches the DOM and re-translates this text when French is on.
  }

  function check() {
    fetch("/api/db-status", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        paint(data && data.connected ? "connected" : "offline");
      })
      .catch(function () { paint("offline"); });
  }

  check();
  setInterval(check, 30000);
})();
