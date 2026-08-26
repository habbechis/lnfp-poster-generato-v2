/* Live Ligue 1 scoreboard (API-Football).
 * Manual refresh only — no automatic polling — so a free-plan key (100
 * requests/day) is spent only when the user asks. One call returns every
 * match, and the server caches it, so rapid clicks don't double-charge.
 */
(() => {
  "use strict";

  const TEAMS = JSON.parse(document.getElementById("teamsData").textContent);
  const BY_CODE = Object.fromEntries(TEAMS.map((t) => [t.code, t]));
  const $ = (s) => document.querySelector(s);
  const board = $("#liveBoard");
  const empty = $("#liveEmpty");
  const tpl = $("#liveMatchTpl");
  const state = $("#liveState");
  const hint = $("#liveHint");
  const meta = $("#liveMeta");
  const refreshBtn = $("#refreshBtn");

  const localLogo = (code) => {
    const t = BY_CODE[code];
    return t ? `/static/${t._logos || "logos"}/${t.logo || code + ".png"}` : "";
  };
  const nameFor = (code, apiName) =>
    (BY_CODE[code] && BY_CODE[code].name_ar) || apiName || "—";

  function setState(kind, text) {
    if (!state) return;
    state.setAttribute("data-state", kind);
    const t = state.querySelector(".db-status__text");
    if (t) t.textContent = text;
  }

  function showMeta(data) {
    if (!meta) return;
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, "0");
    const mm = String(now.getMinutes()).padStart(2, "0");
    let txt = `آخر تحديث ${hh}:${mm}`;
    const q = data && data.quota;
    if (q && q.remaining != null) {
      txt += ` — ${q.remaining} طلب متبقٍّ اليوم`;
    }
    meta.textContent = txt;
  }

  function statusLabel(m) {
    if (m.live) return m.elapsed != null ? `مباشر ${m.elapsed}'` : "مباشر";
    if (m.finished) return "انتهت";
    if (m.status === "HT") return "الاستراحة";
    if (m.status === "NS") return "لم تبدأ";
    if (m.status === "PST") return "مؤجّلة";
    return m.status_long || m.status || "";
  }

  function card(m) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    const home = node.querySelector(".live-match__side--home");
    const away = node.querySelector(".live-match__side--away");
    home.querySelector(".live-match__logo").style.backgroundImage =
      `url("${localLogo(m.home) || m.home_logo || ""}")`;
    away.querySelector(".live-match__logo").style.backgroundImage =
      `url("${localLogo(m.away) || m.away_logo || ""}")`;
    home.querySelector(".live-match__name").textContent =
      nameFor(m.home, m.home_name);
    away.querySelector(".live-match__name").textContent =
      nameFor(m.away, m.away_name);
    const sh = m.score_home == null ? "–" : m.score_home;
    const sa = m.score_away == null ? "–" : m.score_away;
    node.querySelector(".live-match__score").textContent = `${sh} - ${sa}`;
    node.querySelector(".live-match__status").textContent = statusLabel(m);
    if (m.live) node.classList.add("is-live");
    else if (m.finished) node.classList.add("is-final");
    return node;
  }

  function render(matches) {
    board.querySelectorAll(".live-match").forEach((n) => n.remove());
    if (!matches.length) {
      empty.textContent = "لا توجد مباريات مباشرة الآن.";
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    const frag = document.createDocumentFragment();
    matches.forEach((m) => frag.appendChild(card(m)));
    board.appendChild(frag);
  }

  async function refresh() {
    if (refreshBtn) refreshBtn.disabled = true;
    setState("checking", "جارٍ التحديث…");
    try {
      const res = await fetch("/api/live/scoreboard",
                             { headers: { Accept: "application/json" } });
      const data = await res.json();
      if (!data.configured) {
        setState("offline", "غير مُفعّل");
        empty.textContent =
          "الميزة غير مُفعّلة — أضِف مفتاح API-Football في الإعدادات.";
        empty.hidden = false;
        board.querySelectorAll(".live-match").forEach((n) => n.remove());
        return;
      }
      showMeta(data);
      if (data.error) {
        setState("offline", "تعذّر التحديث");
        hint.textContent = data.error;
        hint.className = "hint is-err";
        return;
      }
      hint.textContent = "";
      hint.className = "hint";
      const matches = data.matches || [];
      const liveN = data.live_count || 0;
      if (liveN) {
        setState("connected", `${liveN} مباراة مباشرة`);
      } else if (matches.length) {
        // TheSportsDB (free) reports results, not in-play — show the count.
        setState("connected", `${matches.length} مباراة`);
      } else {
        setState("checking", "لا نتائج بعد");
      }
      render(matches);
    } catch (err) {
      setState("offline", "تعذّر التحديث");
      hint.textContent = "تعذّر الاتصال.";
      hint.className = "hint is-err";
    } finally {
      if (refreshBtn) refreshBtn.disabled = false;
    }
  }

  if (refreshBtn) refreshBtn.addEventListener("click", refresh);
  // One automatic load when the page opens; after that it's manual only.
  refresh();
})();
