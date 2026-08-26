/* =========================================================================
   LNFP Standings editor — drag to reorder, edit points, save & export
   ========================================================================= */
(() => {
  "use strict";

  const TEAMS = JSON.parse(document.getElementById("teamsData").textContent);
  const TEAM_BY_CODE = Object.fromEntries(TEAMS.map((t) => [t.code, t]));
  const CTX = (() => {
    const elx = document.getElementById("rankCtx");
    try { return (elx && JSON.parse(elx.textContent)) || {}; }
    catch { return {}; }
  })();

  const $ = (s, r = document) => r.querySelector(s);
  const el = {
    list: $("#rankList"),
    rowTpl: $("#rankRowTpl"),
    sort: $("#sortBtn"),
    reset: $("#resetBtn"),
    fetchApi: $("#fetchApiBtn"),
    played: $("#playedInput"),
    save: $("#saveBtn"),
    download: $("#downloadBtn"),
    downloadAll: $("#downloadAllBtn"),
    hint: $("#hint"),
    previewImg: $("#previewImg"),
    previewEmpty: $("#previewEmpty"),
    previewBadge: $("#previewBadge"),
    previewSpinner: $("#previewSpinner"),
  };

  let previewTimer = null;
  let currentBlobUrl = null;
  let previewAbort = null;
  let previewSeq = 0;

  const logoUrl = (code) => {
    const t = TEAM_BY_CODE[code];
    if (!t) return "";
    return `/static/${t._logos || "logos"}/${t.logo || code + ".png"}`;
  };

  /* ------------------------------------------------------------------ */
  /* Build & render                                                      */
  /* ------------------------------------------------------------------ */
  function defaultRows() {
    return TEAMS.map((t) => ({ code: t.code, points: 0, played: 0 }));
  }

  /** Merge a saved table with the live roster: keep saved order and points,
      drop teams no longer in the pool, append any newcomers at the end. */
  function mergeRows(saved) {
    const known = new Set(TEAMS.map((t) => t.code));
    const seen = new Set();
    const rows = [];
    (saved || []).forEach((r) => {
      if (known.has(r.code) && !seen.has(r.code)) {
        seen.add(r.code);
        rows.push({ code: r.code, points: parseInt(r.points, 10) || 0,
                    played: parseInt(r.played, 10) || 0 });
      }
    });
    TEAMS.forEach((t) => {
      if (!seen.has(t.code)) rows.push({ code: t.code, points: 0, played: 0 });
    });
    return rows;
  }

  function render(rows) {
    el.list.innerHTML = "";
    rows.forEach((r) => {
      const row = el.rowTpl.content.firstElementChild.cloneNode(true);
      row.dataset.code = r.code;
      const t = TEAM_BY_CODE[r.code] || {};
      row.querySelector(".rank-row__logo").style.backgroundImage =
        `url("${logoUrl(r.code)}")`;
      row.querySelector(".rank-row__name").textContent = t.name_ar || r.code;
      // Zero shows as the faded placeholder, so there is no real 0 to erase.
      const pts = row.querySelector(".rank-row__pts");
      pts.value = r.points ? r.points : "";
      pts.addEventListener("input", () => {
        pts.value = pts.value.replace(/[^0-9]/g, "").slice(0, 3);
        schedulePreview();
      });
      const played = row.querySelector(".rank-row__played");
      played.value = r.played ? r.played : "";
      played.addEventListener("input", () => {
        played.value = played.value.replace(/[^0-9]/g, "").slice(0, 2);
        schedulePreview();
      });
      wireMove(row);
      el.list.appendChild(row);
    });
    renumber();
  }

  function renumber() {
    [...el.list.children].forEach((row, i) => {
      row.querySelector(".rank-row__pos").textContent = i + 1;
    });
  }

  /** Read the current DOM order into a plain array. */
  function collect() {
    return [...el.list.children].map((row) => ({
      code: row.dataset.code,
      points: parseInt(row.querySelector(".rank-row__pts").value, 10) || 0,
      played: parseInt(row.querySelector(".rank-row__played").value, 10) || 0,
    }));
  }

  /* ------------------------------------------------------------------ */
  /* Reordering — up/down arrows (reliable on desktop and mobile alike). */
  /* ------------------------------------------------------------------ */
  function wireMove(row) {
    row.querySelectorAll(".rank-move").forEach((btn) => {
      btn.addEventListener("click", () => moveRow(row, btn.dataset.move));
    });
  }

  function moveRow(row, dir) {
    if (dir === "up") {
      const prev = row.previousElementSibling;
      if (prev) el.list.insertBefore(row, prev);
    } else {
      const next = row.nextElementSibling;
      if (next) el.list.insertBefore(next, row);   // move next above -> row down
    }
    renumber();
    schedulePreview();
  }

  /* ------------------------------------------------------------------ */
  /* Preview / export                                                    */
  /* ------------------------------------------------------------------ */
  const currentPage = () =>
    (document.querySelector('input[name="rankPage"]:checked') || {}).value || "1";

  function payload() {
    return { league: CTX.league, title: "الترتيب العام",
             subtitle: CTX.subtitle || "", rows: collect(),
             page: currentPage() };
  }

  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(updatePreview, 300);
  }

  async function updatePreview() {
    if (previewAbort) previewAbort.abort();
    const ctrl = new AbortController();
    previewAbort = ctrl;
    const seq = ++previewSeq;
    setSpinner(true); setBadge("جارٍ التوليد…", "loading");
    try {
      const res = await fetch("/api/standings/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(await errorText(res));
      const blob = await res.blob();
      if (seq !== previewSeq) return;
      if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl);
      currentBlobUrl = URL.createObjectURL(blob);
      await new Promise((resolve) => {
        el.previewImg.onload = el.previewImg.onerror = resolve;
        el.previewImg.src = currentBlobUrl;
      });
      if (seq !== previewSeq) return;
      el.previewImg.hidden = false;
      el.previewEmpty.hidden = true;
      setBadge("جاهز", "ok");
    } catch (err) {
      if (err.name === "AbortError") return;
      setBadge("خطأ", "err");
      el.previewEmpty.textContent = "تعذّر توليد المعاينة.";
      el.previewEmpty.hidden = false;
      el.previewImg.hidden = true;
    } finally {
      if (seq === previewSeq) { setSpinner(false); previewAbort = null; }
    }
  }

  function saveBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }

  async function download() {
    hint("جارٍ تجهيز الصفحة الحالية…");
    try {
      const res = await fetch("/api/standings/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      if (!res.ok) throw new Error(await errorText(res));
      saveBlob(await res.blob(), `classement-${CTX.league}-${currentPage()}.png`);
      hint("تم تحميل الصفحة بنجاح.", "ok");
    } catch (err) {
      hint(err.message, "err");
    }
  }

  // Both pages as a single ZIP — one download that works on mobile too.
  async function downloadAll() {
    hint("جارٍ تجهيز الصفحتين…");
    try {
      const res = await fetch("/api/standings/generate_all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      if (!res.ok) throw new Error(await errorText(res));
      saveBlob(await res.blob(), `classement-${CTX.league}.zip`);
      hint("تم تحميل الصفحتين.", "ok");
    } catch (err) {
      hint(err.message, "err");
    }
  }

  async function save() {
    try {
      const res = await fetch("/api/standings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      if (!res.ok) throw new Error(await errorText(res));
      hint("تم حفظ الترتيب.", "ok");
    } catch (err) {
      hint("تعذّر الحفظ.", "err");
    }
  }

  /* ------------------------------------------------------------------ */
  /* Helpers                                                             */
  /* ------------------------------------------------------------------ */
  function setSpinner(on) { el.previewSpinner.hidden = !on; }
  function setBadge(text, kind) {
    el.previewBadge.textContent = text;
    el.previewBadge.className = "badge" + (kind === "ok" ? "" : ` is-${kind}`);
  }
  let hintTimer;
  function hint(text, kind = "") {
    el.hint.textContent = text;
    el.hint.className = "hint" + (kind ? ` is-${kind}` : "");
    clearTimeout(hintTimer);
    if (kind === "ok") hintTimer = setTimeout(() => { el.hint.textContent = ""; }, 4000);
  }
  async function errorText(res) {
    try {
      const d = await res.clone().json();
      return d.detail || d.error || `HTTP ${res.status}`;
    } catch { return `HTTP ${res.status}`; }
  }

  /* ------------------------------------------------------------------ */
  /* Wiring                                                              */
  /* ------------------------------------------------------------------ */
  el.sort.addEventListener("click", () => {
    const rows = collect().sort((a, b) => b.points - a.points);
    render(rows);
    schedulePreview();
  });
  el.reset.addEventListener("click", () => {
    if (!confirm("استعادة الترتيب إلى القائمة الأصلية بنقاط صفر؟")) return;
    render(defaultRows());
    schedulePreview();
  });
  if (el.fetchApi) el.fetchApi.addEventListener("click", fetchFromApi);
  const parseBtn = $("#parseBulletinBtn");
  if (parseBtn) parseBtn.addEventListener("click", parseBulletin);

  /** Apply parsed standing rows: set points (and games played, when the text
      names its match-day) and order by the parsed sequence, keeping any team
      the text didn't mention at its current values. */
  function applyStandings(rows, matchday) {
    const byCode = Object.fromEntries(rows.map((r, i) => [r.code, { ...r, i }]));
    const merged = collect().map((r) => {
      const p = byCode[r.code];
      if (!p) return { ...r, rank: 999 };
      return { code: r.code, points: p.points, rank: p.i,
               played: matchday || r.played };
    });
    merged.sort((a, b) => a.rank - b.rank);
    render(merged);
    // Keep the "fill all" box in step with what was just applied.
    if (matchday && el.played) el.played.value = matchday;
    schedulePreview();
  }

  async function parseBulletin() {
    const box = $("#bulletinText");
    const text = (box && box.value || "").trim();
    if (!text) { hint("الصق نصّ الترتيب أولاً.", "err"); return; }
    parseBtn.disabled = true;
    hint("جارٍ التحليل…");
    try {
      const res = await fetch("/api/parse-results", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, squad: CTX.league }),
      });
      const data = await res.json();
      const rows = data.standings || [];
      if (!rows.length) {
        hint(data.unknown && data.unknown.length
          ? `لم يُتعرَّف على أي صف. رموز غير معروفة: ${data.unknown.join("، ")}`
          : "لم يُتعرَّف على أي صف ترتيب في النص.", "err");
        return;
      }
      applyStandings(rows, data.matchday);
      let extra = "";
      if (data.matchday) extra += ` — عدد المباريات: ${data.matchday}`;
      if ((data.foreign || []).length)
        extra += ` — خارج هذه البطولة: ${data.foreign.join("، ")}`;
      if ((data.unknown || []).length)
        extra += ` — رموز غير معروفة: ${data.unknown.join("، ")}`;
      const clean = !(data.foreign || []).length && !(data.unknown || []).length;
      hint(`تم تعبئة ${rows.length} فريقاً.${extra}`, clean ? "ok" : "");
    } catch (err) {
      hint("تعذّر تحليل النص.", "err");
    } finally {
      parseBtn.disabled = false;
    }
  }

  /** Standings parsed in the studio are handed over via sessionStorage. */
  function consumeHandoff() {
    let payload = null;
    try {
      const raw = sessionStorage.getItem("lnfp-parsed-standings");
      if (raw) payload = JSON.parse(raw);
      sessionStorage.removeItem("lnfp-parsed-standings");
    } catch (e) { return; }
    // Older handoffs stored a bare array; accept both shapes.
    const rows = Array.isArray(payload) ? payload : (payload && payload.rows);
    if (!rows || !rows.length) return;
    const matchday = Array.isArray(payload) ? null : (payload.matchday || null);
    applyStandings(rows, matchday);
    hint(`تم تطبيق ${rows.length} صفاً من النص الملصوق في المحرّر.`, "ok");
  }

  /** Pull the live table from API-Football and fill points/played, ordered by
      the API's rank. Teams the API doesn't return keep their current values. */
  async function fetchFromApi() {
    el.fetchApi.disabled = true;
    hint("جارٍ الجلب من API-Football…");
    try {
      const res = await fetch("/api/live/standings");
      const data = await res.json();
      if (!data.configured) {
        hint("الميزة غير مُفعّلة — أضِف مفتاح API-Football.", "err");
        return;
      }
      if (data.error) { hint(data.error, "err"); return; }
      const rows = data.rows || [];
      if (!rows.length) { hint("لم تُرجِع الواجهة أي صفوف.", "err"); return; }
      const byCode = Object.fromEntries(rows.map((r) => [r.code, r]));
      // Keep current values for any team the API omitted, then order by rank.
      const merged = collect().map((r) => {
        const api = byCode[r.code];
        return api ? { code: r.code, points: api.points || 0,
                       played: api.played || 0, rank: api.rank || 999 }
                   : { ...r, rank: 999 };
      });
      merged.sort((a, b) => a.rank - b.rank);
      render(merged);
      schedulePreview();
      hint(`تم جلب ${rows.length} فريقاً من API-Football.`, "ok");
    } catch (err) {
      hint("تعذّر الاتصال بـ API-Football.", "err");
    } finally {
      el.fetchApi.disabled = false;
    }
  }
  el.save.addEventListener("click", save);
  el.download.addEventListener("click", download);
  el.downloadAll.addEventListener("click", downloadAll);
  // A convenience: fill every club's "played" with one value; each row can
  // then be overridden individually.
  el.played.addEventListener("input", () => {
    el.played.value = el.played.value.replace(/[^0-9]/g, "").slice(0, 2);
    const v = el.played.value;
    el.list.querySelectorAll(".rank-row__played").forEach((inp) => {
      inp.value = v;
    });
    schedulePreview();
  });
  document.querySelectorAll('input[name="rankPage"]').forEach((r) =>
    r.addEventListener("change", updatePreview));

  /* ------------------------------------------------------------------ */
  /* Init: load the saved table for this league, else the roster         */
  /* ------------------------------------------------------------------ */
  async function init() {
    let saved = null;
    try {
      const res = await fetch(`/api/standings/${CTX.league}`);
      if (res.ok) saved = (await res.json()).rows;
    } catch { /* fall back to roster */ }
    render(saved && saved.length ? mergeRows(saved) : defaultRows());
    consumeHandoff();          // standings pasted in the studio, if any
    updatePreview();
  }

  init();
})();
