/* =========================================================================
   LNFP Poster Generator — front-end controller
   ========================================================================= */
(() => {
  "use strict";

  const TEAMS = JSON.parse(document.getElementById("teamsData").textContent);
  const TEAM_BY_CODE = Object.fromEntries(TEAMS.map((t) => [t.code, t]));
  const SELECTED_COMP = (() => {
    const el = document.getElementById("selectedComp");
    try { return el ? JSON.parse(el.textContent) : "ligue1"; }
    catch { return "ligue1"; }
  })();
  const CTX = (() => {
    const el = document.getElementById("renderCtx");
    try { return (el && JSON.parse(el.textContent)) || {}; }
    catch { return {}; }
  })();

  // Tunisian Arabic date labels (mirrors app/services/dates.py).
  const WEEKDAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"];
  const MONTHS = ["جانفي", "فيفري", "مارس", "أفريل", "ماي", "جوان", "جويلية", "أوت", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];

  const $ = (sel, root = document) => root.querySelector(sel);
  const el = {
    competition: $("#competition"),
    brandPreview: $("#brandPreview"),
    brandUpload: $("#brandUpload"),
    brandReset: $("#brandReset"),
    title: $("#title"),
    titleAutoHelp: $("#titleAutoHelp"),
    titleControls: $("#titleControls"),
    titleFont: $("#titleFont"),
    titleSize: $("#titleSize"),
    titleSizeVal: $("#titleSizeVal"),
    date: $("#matchDate"),
    datePreview: $("#datePreview"),
    matchList: $("#matchList"),
    addMatch: $("#addMatch"),
    download: $("#downloadBtn"),
    save: $("#saveBtn"),
    load: $("#loadBtn"),
    hint: $("#hint"),
    previewImg: $("#previewImg"),
    previewEmpty: $("#previewEmpty"),
    previewBadge: $("#previewBadge"),
    previewSpinner: $("#previewSpinner"),
    rowTpl: $("#matchRowTpl"),
    teamMenu: $("#teamMenu"),
    teamSearch: $("#teamSearch"),
    teamOptions: $("#teamOptions"),
    channelMenu: $("#channelMenu"),
    channelOptions: $("#channelOptions"),
    channelCount: $("#channelCount"),
    savedDialog: $("#savedDialog"),
    savedList: $("#savedList"),
    status: $("#storeStatus"),
    siteLogo: $("#siteLogo"),
    sidebarComps: $("#sidebarComps"),
  };

  // In-memory model: one entry per fixture row.
  let matches = [];
  let kickoffDays = [];   // KICK OFF: [{date_label, matches:[{home,away,time}]}]
  let activePicker = null; // { index, side }
  let currentBlobUrl = null;
  let previewTimer = null;
  let competitions = [];
  let channels = [];            // registry, as served
  let maxChannels = 4;
  let activeChannelRow = null;  // index of the match whose menu is open
  // Built-in file name or an uploaded data: URL; the squad sets the default.
  let brandLogo = CTX.brand || "logo-ligue1.png";
  let previewAbort = null;           // cancels the in-flight preview request
  let previewSeq = 0;                // only the newest response may paint

  // Each team carries its logo file and the static folder it lives in
  // (Ligue 1 in "logos", Ligue 2 pools in "logos-l2").
  const logoUrl = (code) => {
    const t = TEAM_BY_CODE[code];
    if (!t) return "";
    const dir = t._logos || "logos";
    const file = t.logo || `${code}.png`;
    return `/static/${dir}/${file}`;
  };

  /* ------------------------------------------------------------------ */
  /* Arabic date label                                                   */
  /* ------------------------------------------------------------------ */
  function arabicDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso + "T00:00:00");
    if (isNaN(d)) return iso;
    const wd = (d.getDay() + 6) % 7; // JS Sun=0 -> our Mon=0
    return `${WEEKDAYS[wd]} ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
  }

  /* ------------------------------------------------------------------ */
  /* Match rows                                                          */
  /* ------------------------------------------------------------------ */
  const RESULTS_TITLE = "نتائج مباريــــــت\nاليــــــــــوم";

  function newMatch(home = null, away = null) {
    return { home, away, time: "16:30", stadium: "", stadiumTouched: false,
             channels: [], scoreHome: "", scoreAway: "" };
  }

  /* ------------------------------------------------------------------ */
  /* Poster type (scheduling / scoring) and title source (auto / manual) */
  /* ------------------------------------------------------------------ */
  // Type drives the layout (score cells vs kickoff time) and, in auto mode,
  // which ready title artwork is used. Source picks that artwork vs typed text.
  const posterTypeVal = () =>
    (document.querySelector('input[name="posterType"]:checked') || {}).value
    || "scheduling";
  const titleModeVal = () =>
    (document.querySelector('input[name="titleMode"]:checked') || {}).value
    || "auto";

  const isResults = () => posterTypeVal() === "scoring";
  const isKickoff = () => posterTypeVal() === "kickoff";

  // The starter text for the manual box: the results heading for a scoring
  // poster, otherwise the competition's own fixtures title.
  function typeDefaultTitle() {
    if (isResults()) return RESULTS_TITLE;
    const c = competitions.find((x) => x.code === el.competition.value);
    return (c && c.title) || el.title.value;
  }

  function effectiveTitle() {
    if (titleModeVal() === "manual") return el.title.value;
    return typeDefaultTitle();
  }

  // Auto mode uses ready title artwork; manual mode renders the typed text.
  function titleImage() {
    if (titleModeVal() === "manual") return "";
    return isResults() ? "title-results.png" : "title-fixtures.png";
  }

  function applyTitleMode() {
    const manual = titleModeVal() === "manual";
    const kickoff = isKickoff();
    el.title.hidden = !manual || kickoff;
    el.titleAutoHelp.hidden = manual || kickoff;
    el.titleControls.hidden = !manual || kickoff;
    const titleField = $("#titleField");
    if (titleField) titleField.hidden = kickoff;
    const kickoffField = $("#kickoffField");
    if (kickoffField) kickoffField.hidden = !kickoff;
    const matchesField = $("#matchesField");
    if (matchesField) matchesField.hidden = kickoff;
    if (!kickoff && manual) el.title.value = typeDefaultTitle();
    const results = isResults();
    const resultsPaste = $("#resultsPasteField");
    const fixturesPaste = $("#fixturesPasteField");
    if (resultsPaste) resultsPaste.hidden = !results;
    if (fixturesPaste) fixturesPaste.hidden = results;
    renderMatches();
    schedulePreview();
  }

  const channelLogo = (code) => {
    const c = channels.find((x) => x.code === code);
    return c ? `/static/tv/${c.logo}` : "";
  };

  function renderMatches() {
    el.matchList.innerHTML = "";
    const results = isResults();
    el.matchList.classList.toggle("is-results", results);
    matches.forEach((m, i) => {
      const row = el.rowTpl.content.firstElementChild.cloneNode(true);
      row.dataset.index = i;
      row.classList.toggle("is-results", results);

      const sh = row.querySelector(".match-score__h");
      const sa = row.querySelector(".match-score__a");
      if (sh && sa) {
        sh.value = m.scoreHome; sa.value = m.scoreAway;
        const clean = (inp, key) => inp.addEventListener("input", () => {
          m[key] = inp.value.replace(/[^0-9]/g, "").slice(0, 2);
          inp.value = m[key]; schedulePreview();
        });
        clean(sh, "scoreHome"); clean(sa, "scoreAway");
      }

      row.querySelectorAll(".team-select").forEach((btn) => {
        const side = btn.closest(".team-pick").dataset.side;
        paintTeamButton(btn, m[side]);
        btn.addEventListener("click", (ev) => {
          ev.stopPropagation();
          openPicker(i, side, btn);
        });
      });

      const time = row.querySelector(".match-time");
      time.value = m.time;
      time.addEventListener("input", () => { m.time = time.value; schedulePreview(); });

      const stadium = row.querySelector(".match-stadium");
      stadium.value = m.stadium;
      stadium.addEventListener("input", () => {
        m.stadium = stadium.value; m.stadiumTouched = true; schedulePreview();
      });

      const tv = row.querySelector(".match-tv");
      if (tv) {
        paintChannels(tv, m);
        tv.addEventListener("click", (ev) => {
          ev.stopPropagation();
          openChannelMenu(i, tv);
        });
      }

      row.querySelector(".match-remove").addEventListener("click", () => {
        matches.splice(i, 1);
        if (matches.length === 0) matches.push(newMatch());
        renderMatches(); schedulePreview();
      });

      el.matchList.appendChild(row);
    });
  }

  function paintTeamButton(btn, code) {
    const logo = btn.querySelector(".team-select__logo");
    const name = btn.querySelector(".team-select__name");
    if (code && TEAM_BY_CODE[code]) {
      btn.classList.remove("is-empty");
      logo.style.backgroundImage = `url("${logoUrl(code)}")`;
      name.textContent = TEAM_BY_CODE[code].name_ar;
    } else {
      btn.classList.add("is-empty");
      logo.style.backgroundImage = "none";
      name.textContent = "اختر فريقاً";
    }
  }

  /* ------------------------------------------------------------------ */
  /* Team picker dropdown                                                */
  /* ------------------------------------------------------------------ */
  function openPicker(index, side, anchor) {
    activePicker = { index, side };
    buildOptions("");
    el.teamSearch.value = "";
    el.teamMenu.hidden = false;
    const r = anchor.getBoundingClientRect();
    const menuW = el.teamMenu.offsetWidth;
    let left = r.left + window.scrollX;
    left = Math.min(left, window.scrollX + document.documentElement.clientWidth - menuW - 8);
    el.teamMenu.style.top = `${r.bottom + window.scrollY + 6}px`;
    el.teamMenu.style.left = `${Math.max(8, left)}px`;
    el.teamSearch.focus();
  }

  function closePicker() {
    el.teamMenu.hidden = true;
    activePicker = null;
  }

  function buildOptions(query) {
    const q = query.trim();
    el.teamOptions.innerHTML = "";
    TEAMS.filter((t) => !q || t.name_ar.includes(q) || t.name_fr.toLowerCase().includes(q.toLowerCase()) || t.short.toLowerCase().includes(q.toLowerCase()))
      .forEach((t) => {
        const li = document.createElement("li");
        li.dir = "auto";                       // Arabic names stay RTL in FR
        li.innerHTML = `<img src="${logoUrl(t.code)}" alt=""><span>${t.name_ar}<span class="sub">${t.name_fr}</span></span>`;
        li.addEventListener("click", () => chooseTeam(t.code));
        el.teamOptions.appendChild(li);
      });
  }

  function chooseTeam(code) {
    if (!activePicker) return;
    const m = matches[activePicker.index];
    m[activePicker.side] = code;
    // Auto-fill stadium from the home team unless the user typed one.
    if (activePicker.side === "home" && !m.stadiumTouched) {
      m.stadium = (TEAM_BY_CODE[code] || {}).stadium_ar || "";
    }
    closePicker();
    renderMatches();
    schedulePreview();
  }

  /* ------------------------------------------------------------------ */
  /* Competitions (title + badge presets)                                */
  /* ------------------------------------------------------------------ */
  async function loadCompetitions() {
    try {
      competitions = await (await fetch("/api/competitions")).json();
    } catch {
      competitions = [];
    }
    el.competition.innerHTML = "";
    competitions.forEach((c) => {
      const o = document.createElement("option");
      o.value = c.code;
      o.textContent = c.name_ar;
      el.competition.appendChild(o);
    });
    // Honour the league picked on the landing page.
    if (competitions.some((c) => c.code === SELECTED_COMP)) {
      el.competition.value = SELECTED_COMP;
    }
    el.competition.addEventListener("change", () => applyCompetition(true));

    // Sidebar chips mirror the dropdown.
    if (el.sidebarComps) {
      el.sidebarComps.addEventListener("click", (e) => {
        const chip = e.target.closest(".comp-chip");
        if (!chip || !chip.dataset.comp) return;   // anchors just navigate
        el.competition.value = chip.dataset.comp;
        applyCompetition(true);
      });
    }
    applyCompetition(false);
  }

  function applyCompetition(rerender) {
    const c = competitions.find((x) => x.code === el.competition.value);
    if (!c) return;
    // Ligue 2 lives in its own squad (pools), so switching to/from it must
    // reload the studio — a client-side preset swap can't change the roster.
    if (rerender) {
      const onL2 = (CTX.squad || "").indexOf("l2-") === 0;
      if (c.code === "ligue2" && !onL2) {
        location.href = "/studio?competition=ligue2&pool=pool1"; return;
      }
      if (c.code === "ligue1" && onL2) {
        location.href = "/studio?competition=ligue1"; return;
      }
    }
    // Don't clobber a title the user typed by hand.
    if (titleModeVal() !== "manual") el.title.value = c.title;
    brandLogo = c.logo;
    paintBrand();
    markActiveChip(c.code);
    if (rerender) schedulePreview();
  }

  function markActiveChip(code) {
    if (!el.sidebarComps) return;
    // Only client-side preset chips carry data-comp; the league nav links are
    // marked active server-side and must be left alone.
    el.sidebarComps.querySelectorAll(".comp-chip[data-comp]").forEach((chip) => {
      chip.classList.toggle("is-active", chip.dataset.comp === code);
    });
  }

  function paintBrand() {
    const src = brandLogo.startsWith("data:") ? brandLogo : `/static/img/${brandLogo}`;
    el.brandPreview.style.backgroundImage = `url("${src}")`;
    // The site header wears the same crest as the poster it is producing.
    if (el.siteLogo) el.siteLogo.src = src;
  }

  function onBrandUpload(ev) {
    const file = ev.target.files && ev.target.files[0];
    if (!file) return;
    if (file.size > 4 * 1024 * 1024) {
      return hint("حجم الشعار كبير جداً (الحد 4 ميغا).", "err");
    }
    const reader = new FileReader();
    reader.onload = () => {
      brandLogo = reader.result;   // data: URL sent with the render payload
      paintBrand();
      schedulePreview();
      hint("تم تحديث الشعار.", "ok");
    };
    reader.onerror = () => hint("تعذّرت قراءة الملف.", "err");
    reader.readAsDataURL(file);
    ev.target.value = "";
  }

  function resetBrand() {
    const c = competitions.find((x) => x.code === el.competition.value);
    brandLogo = (c && c.logo) || CTX.brand || "logo-ligue1.png";
    paintBrand();
    schedulePreview();
  }

  /* ------------------------------------------------------------------ */
  /* Title face + size                                                   */
  /* ------------------------------------------------------------------ */
  async function loadFonts() {
    let fonts = [];
    try {
      fonts = await (await fetch("/api/fonts")).json();
    } catch { fonts = []; }
    el.titleFont.innerHTML = "";
    fonts.forEach((f) => {
      const o = document.createElement("option");
      o.value = f.id;
      o.textContent = f.label;
      el.titleFont.appendChild(o);
    });
    el.titleFont.disabled = fonts.length < 2;
  }

  function updateTitleSizeLabel() {
    el.titleSizeVal.textContent =
      `${Math.round(parseFloat(el.titleSize.value) * 100)}%`;
  }

  /* ------------------------------------------------------------------ */
  /* Broadcasters                                                        */
  /* ------------------------------------------------------------------ */
  async function loadChannels() {
    try {
      const data = await (await fetch("/api/channels")).json();
      channels = data.channels || [];
      maxChannels = data.max_per_match || 4;
    } catch {
      channels = [];
    }
  }

  /** Show the picked marks on the row button, or a prompt when empty. */
  function paintChannels(btn, m) {
    const box = btn.querySelector(".match-tv__logos");
    const label = btn.querySelector(".match-tv__label");
    const picked = m.channels || [];
    box.innerHTML = "";
    picked.forEach((code) => {
      const img = document.createElement("img");
      img.src = channelLogo(code);
      img.alt = "";
      box.appendChild(img);
    });
    label.hidden = picked.length > 0;
    btn.classList.toggle("is-set", picked.length > 0);
  }

  function openChannelMenu(index, anchor) {
    activeChannelRow = index;
    renderChannelOptions();
    el.channelMenu.hidden = false;
    const r = anchor.getBoundingClientRect();
    const w = el.channelMenu.offsetWidth;
    let left = Math.min(r.left + window.scrollX,
                        window.scrollX + document.documentElement.clientWidth - w - 8);
    el.channelMenu.style.top = `${r.bottom + window.scrollY + 6}px`;
    el.channelMenu.style.left = `${Math.max(8, left)}px`;
  }

  function closeChannelMenu() {
    el.channelMenu.hidden = true;
    activeChannelRow = null;
  }

  function renderChannelOptions() {
    const m = matches[activeChannelRow];
    if (!m) return;
    const picked = m.channels || [];
    el.channelCount.textContent = `(${picked.length}/${maxChannels})`;
    el.channelOptions.innerHTML = "";
    channels.forEach((c) => {
      const on = picked.includes(c.code);
      // Once the cap is reached, the unpicked ones go quiet rather than
      // silently doing nothing when clicked.
      const full = !on && picked.length >= maxChannels;
      const li = document.createElement("li");
      li.dir = "auto";                         // Arabic channel names stay RTL
      li.className = "channel-opt" + (full ? " is-disabled" : "");
      li.innerHTML = `
        <span class="channel-opt__box${on ? " is-on" : ""}" aria-hidden="true"></span>
        <img src="/static/tv/${c.logo}" alt="">
        <span class="channel-opt__name">${c.name_ar}</span>`;
      li.setAttribute("role", "checkbox");
      li.setAttribute("aria-checked", String(on));
      // Stop the bubble: the click re-renders this list, so by the time the
      // document handler ran the node would be detached and the outside-click
      // check would close the menu mid-selection.
      if (!full) li.addEventListener("click", (ev) => {
        ev.stopPropagation();
        toggleChannel(c.code);
      });
      el.channelOptions.appendChild(li);
    });
  }

  function toggleChannel(code) {
    const m = matches[activeChannelRow];
    if (!m) return;
    const picked = m.channels || (m.channels = []);
    const at = picked.indexOf(code);
    if (at >= 0) picked.splice(at, 1);
    else if (picked.length < maxChannels) picked.push(code);
    renderChannelOptions();
    const btn = el.matchList.querySelector(
      `.match-row[data-index="${activeChannelRow}"] .match-tv`);
    if (btn) paintChannels(btn, m);
    schedulePreview();
  }

  /* ------------------------------------------------------------------ */
  /* Payload + preview                                                   */
  /* ------------------------------------------------------------------ */
  function buildPayload() {
    return {
      title: effectiveTitle(),
      title_image: titleImage(),
      mode: isResults() ? "results" : "fixtures",
      date_iso: el.date.value,
      date_label: arabicDate(el.date.value),
      competition: el.competition.value,
      brand_logo: brandLogo,
      background: CTX.background || "",
      title_size: parseFloat(el.titleSize.value) || 1,
      title_font: el.titleFont.value || "",
      matches: matches
        .filter((m) => m.home && m.away)
        .map((m) => ({ home: m.home, away: m.away, time: m.time,
                       stadium_ar: m.stadium, channels: m.channels || [],
                       score_home: m.scoreHome, score_away: m.scoreAway })),
    };
  }

  function schedulePreview() {
    el.datePreview.textContent = arabicDate(el.date.value);
    clearTimeout(previewTimer);
    previewTimer = setTimeout(updatePreview, 350);
  }

  async function updatePreview() {
    if (isKickoff()) return updateKickoffPreview();
    const payload = buildPayload();
    if (payload.matches.length === 0) {
      setBadge("أضف مباراة", "loading");
      showEmpty("اختر الفرق لعرض المعاينة…");
      return;
    }
    // Supersede any request still in flight: on a slow host their responses
    // arrive out of order, which used to leave the spinner running forever.
    if (previewAbort) previewAbort.abort();
    const ctrl = new AbortController();
    previewAbort = ctrl;
    const seq = ++previewSeq;

    setSpinner(true); setBadge("جارٍ التوليد…", "loading");
    try {
      const res = await fetch("/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(await errorText(res));
      const blob = await res.blob();
      if (seq !== previewSeq) return;          // a newer render won
      if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl);
      currentBlobUrl = URL.createObjectURL(blob);
      // Only reveal once the browser has actually decoded the PNG.
      await new Promise((resolve) => {
        el.previewImg.onload = el.previewImg.onerror = resolve;
        el.previewImg.src = currentBlobUrl;
      });
      if (seq !== previewSeq) return;
      el.previewImg.hidden = false;
      el.previewEmpty.hidden = true;
      setBadge("جاهز", "ok");
    } catch (err) {
      if (err.name === "AbortError") return;   // superseded; keep the spinner
      setBadge("خطأ", "err");
      showEmpty("تعذّر توليد المعاينة.");
      hint(err.message, "err");
    } finally {
      // Whichever request is newest owns the spinner.
      if (seq === previewSeq) { setSpinner(false); previewAbort = null; }
    }
  }

  /* ------------------------------------------------------------------ */
  /* KICK OFF: preview + download (own endpoints, own payload shape)     */
  /* ------------------------------------------------------------------ */
  function buildKickoffPayload() {
    const mw = parseInt(($("#matchweek") || {}).value, 10) || 1;
    return {
      matchweek: mw,
      brand_logo: brandLogo,
      background: CTX.background || "",
      days: kickoffDays,
    };
  }

  async function updateKickoffPreview() {
    const payload = buildKickoffPayload();
    if (!payload.days.length) {
      setBadge("أضف مباريات", "loading");
      showEmpty("الصق نصّ تعيينات الجولة لعرض المعاينة…");
      return;
    }
    if (previewAbort) previewAbort.abort();
    const ctrl = new AbortController();
    previewAbort = ctrl;
    const seq = ++previewSeq;
    setSpinner(true); setBadge("جارٍ التوليد…", "loading");
    try {
      const res = await fetch("/api/kickoff/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
      showEmpty("تعذّر توليد المعاينة.");
      hint(err.message, "err");
    } finally {
      if (seq === previewSeq) { setSpinner(false); previewAbort = null; }
    }
  }

  async function downloadKickoff() {
    const payload = buildKickoffPayload();
    if (!payload.days.length) return hint("الصق تعيينات الجولة أولاً.", "err");
    hint("جارٍ تجهيز الملف بدقة كاملة…");
    try {
      const res = await fetch("/api/kickoff/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await errorText(res));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lnfp-kickoff-${payload.matchweek}.png`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      hint("تم تحميل الأفيش بنجاح.", "ok");
    } catch (err) {
      hint(err.message, "err");
    }
  }

  function showEmpty(text) {
    el.previewEmpty.textContent = text;
    el.previewEmpty.hidden = false;
    el.previewImg.hidden = true;
  }

  /** Pull a useful message out of a failed response (JSON or plain text). */
  async function errorText(res) {
    try {
      const data = await res.clone().json();
      return data.detail || data.error || `HTTP ${res.status}`;
    } catch {
      return `HTTP ${res.status}`;
    }
  }

  async function download() {
    if (isKickoff()) return downloadKickoff();
    const payload = buildPayload();
    if (payload.matches.length === 0) return hint("أضف مباراة واحدة على الأقل.", "err");
    hint("جارٍ تجهيز الملف بدقة كاملة…");
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await errorText(res));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lnfp-${payload.date_iso || "affiche"}.png`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      hint("تم تحميل الأفيش بنجاح.", "ok");
    } catch (err) {
      hint(err.message, "err");
    }
  }

  /* ------------------------------------------------------------------ */
  /* Save / load (Firebase or local via the API)                         */
  /* ------------------------------------------------------------------ */
  async function save() {
    const payload = buildPayload();
    if (payload.matches.length === 0) return hint("لا يمكن حفظ أفيش فارغ.", "err");
    try {
      const res = await fetch("/api/matchdays", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      hint(`تم الحفظ (${data.id}).`, "ok");
    } catch (err) {
      hint("تعذّر الحفظ.", "err");
    }
  }

  async function openSaved() {
    el.savedList.innerHTML = `<li class="saved-empty">جارٍ التحميل…</li>`;
    el.savedDialog.showModal();
    try {
      const res = await fetch("/api/matchdays");
      const items = await res.json();
      if (!items.length) {
        el.savedList.innerHTML = `<li class="saved-empty">لا توجد أفيشات محفوظة بعد.</li>`;
        return;
      }
      el.savedList.innerHTML = "";
      items.forEach((it) => {
        const li = document.createElement("li");
        li.dir = "auto";                       // Arabic date labels stay RTL
        const label = (it.date_label || it.date_iso || "بدون تاريخ");
        li.innerHTML = `
          <div class="meta"><strong>${label}</strong>
            <span>${(it.matches || []).length} مباريات</span></div>
          <div class="row-actions">
            <button class="btn btn--gold" data-act="load">تحميل</button>
            <button class="icon-btn icon-btn--danger" data-act="del" title="حذف">&times;</button>
          </div>`;
        li.querySelector('[data-act="load"]').addEventListener("click", () => loadMatchday(it));
        li.querySelector('[data-act="del"]').addEventListener("click", () => deleteMatchday(it.id, li));
        el.savedList.appendChild(li);
      });
    } catch (err) {
      el.savedList.innerHTML = `<li class="saved-empty">تعذّر التحميل.</li>`;
    }
  }

  function loadMatchday(it) {
    el.title.value = it.title || el.title.value;
    if (it.date_iso) el.date.value = it.date_iso;
    if (it.competition) el.competition.value = it.competition;
    if (it.brand_logo) { brandLogo = it.brand_logo; paintBrand(); }
    if (it.title_size) { el.titleSize.value = it.title_size; updateTitleSizeLabel(); }
    if (it.title_font && [...el.titleFont.options].some((o) => o.value === it.title_font))
      el.titleFont.value = it.title_font;
    matches = (it.matches || []).map((m) => ({
      home: m.home, away: m.away, time: m.time || "16:30",
      stadium: m.stadium_ar || "", stadiumTouched: !!m.stadium_ar,
      channels: Array.isArray(m.channels) ? m.channels.slice(0, maxChannels) : [],
      scoreHome: (m.score_home || "").toString(),
      scoreAway: (m.score_away || "").toString(),
    }));
    if (matches.length === 0) matches.push(newMatch());
    // Restore the poster type (scheduling/scoring) and the title source.
    const results = it.mode === "results";
    const typeRadio = document.querySelector(
      `input[name="posterType"][value="${results ? "scoring" : "scheduling"}"]`);
    if (typeRadio) typeRadio.checked = true;
    const source = it.title_image ? "auto" : "manual";
    const srcRadio = document.querySelector(
      `input[name="titleMode"][value="${source}"]`);
    if (srcRadio) srcRadio.checked = true;
    applyTitleMode();
    el.savedDialog.close();
    hint("تم تحميل الأفيش المحفوظ.", "ok");
  }

  /** Pull the day's Ligue 1 fixtures (with scores) from API-Football and load
      them as scoring rows. Only matches whose clubs map to our roster are
      kept; the date comes from the date picker. */
  async function fetchScores() {
    const btn = $("#fetchScoresBtn");
    if (btn) btn.disabled = true;
    hint("جارٍ جلب النتائج من API-Football…");
    try {
      const url = "/api/live/fixtures?date=" +
                  encodeURIComponent(el.date.value || "");
      const data = await (await fetch(url)).json();
      if (!data.configured) {
        hint("الميزة غير مُفعّلة — أضِف مفتاح API-Football.", "err");
        return;
      }
      if (data.error) { hint(data.error, "err"); return; }
      const fx = (data.matches || []).filter((m) => m.home && m.away);
      if (!fx.length) {
        hint("لا توجد مباريات مطابقة في هذا التاريخ.", "err");
        return;
      }
      matches = fx.map((m) => {
        const nm = newMatch(m.home, m.away);
        nm.scoreHome = m.score_home == null ? "" : String(m.score_home);
        nm.scoreAway = m.score_away == null ? "" : String(m.score_away);
        return nm;
      });
      // Switch to the scoring layout so the result cells show.
      const typeRadio = document.querySelector(
        'input[name="posterType"][value="scoring"]');
      if (typeRadio) typeRadio.checked = true;
      applyTitleMode();          // re-renders match rows + refreshes preview
      hint(`تم جلب ${fx.length} مباراة.`, "ok");
    } catch (err) {
      hint("تعذّر الاتصال بـ API-Football.", "err");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  /** Parse a pasted results bulletin: fill the match rows and scores, pick the
      teams from their acronyms, and switch to the scoring layout. Standings in
      the same text are saved so the ranking page picks them up. */
  async function parseBulletin() {
    const box = $("#bulletinText");
    const btn = $("#parseBulletinBtn");
    const out = $("#bulletinHint");
    const text = (box && box.value || "").trim();
    const say = (msg, kind) => {
      if (!out) return;
      out.textContent = msg;
      out.className = "hint" + (kind ? ` is-${kind}` : "");
    };
    if (!text) { say("الصق نصّ النتائج أولاً.", "err"); return; }
    if (btn) btn.disabled = true;
    say("جارٍ التحليل…");
    try {
      const res = await fetch("/api/parse-results", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, squad: CTX.squad || "ligue1" }),
      });
      const data = await res.json();
      const usable = (data.matches || []).filter((m) => m.home && m.away);
      if (!usable.length) {
        say((data.unknown || []).length
          ? `لم يُتعرَّف على أي مباراة. رموز غير معروفة: ${data.unknown.join("، ")}`
          : "لم يُتعرَّف على أي مباراة في النص.", "err");
        return;
      }
      matches = usable.map((m) => {
        const nm = newMatch(m.home, m.away);
        nm.scoreHome = String(m.score_home);
        nm.scoreAway = String(m.score_away);
        return nm;
      });
      // Results text implies a scoring poster.
      const typeRadio = document.querySelector(
        'input[name="posterType"][value="scoring"]');
      if (typeRadio) typeRadio.checked = true;
      applyTitleMode();               // re-renders rows + refreshes the preview
      // In manual title mode, seed the heading with the parsed round.
      if (titleModeVal() === "manual" && data.title_ar) {
        el.title.value = data.title_ar;
        schedulePreview();
      }
      // Hand any parsed table to the ranking page.
      if ((data.standings || []).length) {
        try {
          sessionStorage.setItem("lnfp-parsed-standings", JSON.stringify({
            rows: data.standings, matchday: data.matchday || null,
          }));
        } catch (e) { /* storage unavailable — skip */ }
      }
      const bits = [`تم استخراج ${usable.length} مباراة`];
      if ((data.standings || []).length)
        bits.push(`و${data.standings.length} صفاً للترتيب`);
      if ((data.foreign || []).length)
        bits.push(`— أندية من خارج هذه البطولة: ${data.foreign.join("، ")}`);
      if ((data.unknown || []).length)
        bits.push(`— رموز غير معروفة: ${data.unknown.join("، ")}`);
      const clean = !(data.unknown || []).length && !(data.foreign || []).length;
      say(bits.join(" "), clean ? "ok" : "");
    } catch (err) {
      say("تعذّر تحليل النص.", "err");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  /* ------------------------------------------------------------------ */
  /* Fixtures bulletin (تعيينات): pasted text or an uploaded PDF          */
  /* ------------------------------------------------------------------ */
  function fixturesHint(msg, kind) {
    const out = $("#fixturesHint");
    if (!out) return;
    out.textContent = msg;
    out.className = "hint" + (kind ? ` is-${kind}` : "");
  }

  /** Load one match day from a parsed bulletin into the editor. */
  function fillFixtures(data) {
    const days = (data.days || []).filter((d) => d.matches.length);
    if (!days.length) {
      fixturesHint((data.unknown || []).length
        ? `لم يُتعرَّف على أي مباراة. غير معروف: ${data.unknown.join("، ")}`
        : "لم يُتعرَّف على أي مباراة في النص.", "err");
      return;
    }
    // A round is split over two days; load the one matching the date picker,
    // otherwise the first — the other days are named in the hint.
    const picked = days.find((d) => d.date_iso === el.date.value) || days[0];
    matches = picked.matches.map((m) => {
      const nm = newMatch(m.home, m.away);
      nm.time = m.time || "16:30";
      nm.stadium = m.stadium_ar || "";
      // The bulletin is authoritative: an unspecified ground stays empty
      // instead of being auto-filled from the home team.
      nm.stadiumTouched = true;
      return nm;
    });
    if (picked.date_iso) el.date.value = picked.date_iso;
    const typeRadio = document.querySelector(
      'input[name="posterType"][value="scheduling"]');
    if (typeRadio) typeRadio.checked = true;
    applyTitleMode();              // re-renders rows + refreshes the preview

    const missing = picked.matches.filter((m) => !m.home || !m.away).length;
    const bits = [`تم تحميل ${picked.matches.length} مباراة`];
    if (picked.date_label) bits.push(`(${picked.date_label})`);
    const others = days.filter((d) => d !== picked);
    if (others.length)
      bits.push(`— أيام أخرى في النص: ${others.map((d) => d.date_iso).join("، ")}؛ غيّر التاريخ ثم أعِد الاستخراج`);
    if (missing) bits.push(`— ${missing} مباراة بفريق غير معروف`);
    if ((data.unknown || []).length)
      bits.push(`— غير معروف: ${data.unknown.join("، ")}`);
    fixturesHint(bits.join(" "), missing || others.length ? "" : "ok");
  }

  /** Same bulletin as fillFixtures(), but keeps every day — not just the one
      matching the date picker — for the KICK OFF round-preview poster. */
  function fillKickoff(data) {
    const days = (data.days || [])
      .filter((d) => d.matches.some((m) => m.home && m.away));
    if (!days.length) {
      fixturesHint((data.unknown || []).length
        ? `لم يُتعرَّف على أي مباراة. غير معروف: ${data.unknown.join("، ")}`
        : "لم يُتعرَّف على أي مباراة في النص.", "err");
      return;
    }
    kickoffDays = days.map((d) => ({
      date_label: d.date_label || "",
      matches: d.matches.filter((m) => m.home && m.away).map((m) => ({
        home: m.home, away: m.away, time: m.time || "16:30",
      })),
    }));
    const total = kickoffDays.reduce((n, d) => n + d.matches.length, 0);
    const missing = days.reduce(
      (n, d) => n + d.matches.filter((m) => !m.home || !m.away).length, 0);
    const bits = [`تم تحميل ${total} مباراة على ${kickoffDays.length} يوم/أيام`];
    if (missing) bits.push(`— ${missing} مباراة بفريق غير معروف`);
    if ((data.unknown || []).length)
      bits.push(`— غير معروف: ${data.unknown.join("، ")}`);
    fixturesHint(bits.join(" "), missing ? "" : "ok");
    schedulePreview();
  }

  async function parseFixturesText() {
    const box = $("#fixturesText");
    const text = (box && box.value || "").trim();
    if (!text) { fixturesHint("الصق نصّ التعيينات أولاً.", "err"); return; }
    const btn = $("#parseFixturesBtn");
    if (btn) btn.disabled = true;
    fixturesHint("جارٍ التحليل…");
    try {
      const res = await fetch("/api/parse-fixtures", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, squad: CTX.squad || "ligue1" }),
      });
      const data = await res.json();
      if (data.error) { fixturesHint(data.error, "err"); return; }
      if (isKickoff()) fillKickoff(data); else fillFixtures(data);
    } catch (err) {
      fixturesHint("تعذّر تحليل النص.", "err");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function parseFixturesPdf(file) {
    if (!file) return;
    fixturesHint("جارٍ قراءة ملف PDF…");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("squad", CTX.squad || "ligue1");
      const res = await fetch("/api/parse-fixtures", { method: "POST", body: fd });
      const data = await res.json();
      if (data.error) { fixturesHint(data.error, "err"); return; }
      if (isKickoff()) fillKickoff(data); else fillFixtures(data);
    } catch (err) {
      fixturesHint("تعذّر قراءة ملف PDF.", "err");
    }
  }

  async function deleteMatchday(id, li) {
    if (!confirm("حذف هذا الأفيش نهائياً؟")) return;
    await fetch(`/api/matchdays/${id}`, { method: "DELETE" });
    li.remove();
    if (!el.savedList.children.length)
      el.savedList.innerHTML = `<li class="saved-empty">لا توجد أفيشات محفوظة بعد.</li>`;
  }

  /* ------------------------------------------------------------------ */
  /* Small helpers                                                       */
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

  async function loadStatus() {
    try {
      const s = await (await fetch("/api/status")).json();
      const cloud = s.backend === "firebase";
      el.status.classList.add(cloud ? "is-cloud" : "is-local");
      el.status.querySelector(".label").textContent =
        cloud ? "متصل بـ Firebase" : "تخزين محلي";
    } catch { /* ignore */ }
  }

  /* ------------------------------------------------------------------ */
  /* Wiring                                                              */
  /* ------------------------------------------------------------------ */
  el.addMatch.addEventListener("click", () => {
    matches.push(newMatch());
    renderMatches();
    schedulePreview();
  });
  const fetchScoresBtn = $("#fetchScoresBtn");
  if (fetchScoresBtn) fetchScoresBtn.addEventListener("click", fetchScores);
  const parseBtn = $("#parseBulletinBtn");
  if (parseBtn) parseBtn.addEventListener("click", parseBulletin);
  const parseFixBtn = $("#parseFixturesBtn");
  if (parseFixBtn) parseFixBtn.addEventListener("click", parseFixturesText);
  const fixturesPdf = $("#fixturesPdf");
  if (fixturesPdf) fixturesPdf.addEventListener("change", (e) => {
    parseFixturesPdf(e.target.files && e.target.files[0]);
    e.target.value = "";            // allow re-picking the same file
  });
  el.title.addEventListener("input", schedulePreview);
  document.querySelectorAll('input[name="titleMode"], input[name="posterType"]')
    .forEach((r) => r.addEventListener("change", applyTitleMode));
  el.titleFont.addEventListener("change", schedulePreview);
  el.titleSize.addEventListener("input", () => {
    updateTitleSizeLabel(); schedulePreview();
  });
  el.date.addEventListener("input", schedulePreview);
  const matchweekInput = $("#matchweek");
  if (matchweekInput) matchweekInput.addEventListener("input", schedulePreview);
  el.brandUpload.addEventListener("change", onBrandUpload);
  el.brandReset.addEventListener("click", resetBrand);
  const navSaved = $("#navSaved");
  const navDownload = $("#navDownload");
  if (navSaved) navSaved.addEventListener("click", openSaved);
  if (navDownload) navDownload.addEventListener("click", download);
  el.download.addEventListener("click", download);
  el.save.addEventListener("click", save);
  el.load.addEventListener("click", openSaved);
  el.teamSearch.addEventListener("input", (e) => buildOptions(e.target.value));
  el.savedDialog.querySelector("[data-close]").addEventListener("click", () => el.savedDialog.close());
  document.addEventListener("click", (e) => {
    // A target already removed from the document came from a menu that
    // re-rendered itself; it is not an outside click.
    if (!document.contains(e.target)) return;
    if (activePicker && !el.teamMenu.contains(e.target)) closePicker();
    if (activeChannelRow !== null && !el.channelMenu.contains(e.target))
      closeChannelMenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && activeChannelRow !== null) closeChannelMenu();
  });
  window.addEventListener("resize", () => {
    if (activePicker) closePicker();
    if (activeChannelRow !== null) closeChannelMenu();
  });

  /* ------------------------------------------------------------------ */
  /* Seed with the reference round so the preview is populated at start  */
  /* ------------------------------------------------------------------ */
  // The opening round is prefilled from whichever roster is loaded, so a
  // Ligue 2 pool starts with its own clubs — never Ligue 1 teams.
  function seedPairs() {
    const ref = [["est", "ess"], ["cab", "asm"], ["esm", "ca"], ["esz", "ob"]];
    if (ref.every(([h, a]) => TEAM_BY_CODE[h] && TEAM_BY_CODE[a])) return ref;
    const codes = TEAMS.map((t) => t.code);
    const pairs = [];
    for (let i = 0; i + 1 < codes.length && pairs.length < 4; i += 2)
      pairs.push([codes[i], codes[i + 1]]);
    return pairs.length ? pairs : [[null, null]];
  }

  async function seed() {
    matches = seedPairs().map(([h, a]) => {
      const m = newMatch(h, a);
      m.stadium = (TEAM_BY_CODE[h] || {}).stadium_ar || "";
      return m;
    });
    renderMatches();
    el.datePreview.textContent = arabicDate(el.date.value);
    updateTitleSizeLabel();
    await loadFonts();
    await loadChannels();
    renderMatches();            // repaint now the channel marks can resolve
    await loadCompetitions();   // sets title + badge from the chosen league
    applyTitleMode();           // sync control visibility to the initial state
    updatePreview();
  }

  seed();
  loadStatus();
})();