/* =========================================================================
   Super-admin control panel: create / reset / suspend / remove accounts.
   ========================================================================= */
(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const el = {
    user: $("#adminUser"), pass: $("#adminPass"),
    gen: $("#genPass"), copy: $("#copyPass"), save: $("#saveAdmin"),
    list: $("#adminList"), hint: $("#adminHint"),
    total: $("#statTotal"), active: $("#statActive"), suspended: $("#statSuspended"),
  };

  // Ambiguous glyphs are omitted, matching the server-side generator.
  const ALPHABET =
    "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%*?-_";

  /** Cryptographically random password — never Math.random for credentials. */
  function generatePassword(len = 16) {
    const out = new Uint32Array(len);
    crypto.getRandomValues(out);
    return Array.from(out, (n) => ALPHABET[n % ALPHABET.length]).join("");
  }

  let hintTimer;
  function hint(text, kind = "") {
    el.hint.textContent = text;
    el.hint.className = "hint" + (kind ? ` is-${kind}` : "");
    clearTimeout(hintTimer);
    if (kind === "ok") hintTimer = setTimeout(() => { el.hint.textContent = ""; }, 5000);
  }

  async function api(url, options) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      ...options,
    });
    if (res.status === 401) { window.location.href = "/"; throw new Error("unauthorised"); }
    let data = null;
    try { data = await res.json(); } catch { /* no body */ }
    if (!res.ok) throw new Error((data && data.error) || `HTTP ${res.status}`);
    return data;
  }

  /* ------------------------------------------------------------------ */
  /* Listing                                                             */
  /* ------------------------------------------------------------------ */
  function fmtDate(ts) {
    if (!ts) return "—";
    return new Date(ts * 1000).toLocaleString("ar-TN", {
      dateStyle: "short", timeStyle: "short",
    });
  }

  async function refresh() {
    try {
      const data = await api("/api/admins");
      el.total.textContent = data.counts.total;
      el.active.textContent = data.counts.active;
      el.suspended.textContent = data.counts.suspended;
      renderList(data.admins);
    } catch (err) {
      el.list.innerHTML = `<li class="saved-empty">تعذّر التحميل.</li>`;
    }
  }

  function renderList(admins) {
    if (!admins.length) {
      el.list.innerHTML = `<li class="saved-empty">لا توجد حسابات بعد.</li>`;
      return;
    }
    el.list.innerHTML = "";
    admins.forEach((a) => {
      const suspended = a.status === "suspended";
      const li = document.createElement("li");
      li.className = "admin-row" + (suspended ? " is-suspended" : "");
      li.innerHTML = `
        <div class="admin-row__id">
          <strong dir="ltr">${a.username}</strong>
          <span class="pill ${suspended ? "pill--amber" : "pill--green"}">
            ${suspended ? "موقوف" : "نشِط"}
          </span>
          <span class="admin-row__meta">آخر دخول: ${fmtDate(a.last_login)}</span>
        </div>
        <div class="admin-row__actions">
          <button type="button" class="btn btn--ghost" data-act="reset">إعادة ضبط</button>
          <button type="button" class="btn btn--ghost" data-act="toggle">
            ${suspended ? "تفعيل" : "إيقاف"}
          </button>
          <button type="button" class="icon-btn icon-btn--danger" data-act="del" title="حذف">&times;</button>
        </div>`;
      li.querySelector('[data-act="reset"]').addEventListener("click", () => prefillReset(a.username));
      li.querySelector('[data-act="toggle"]').addEventListener("click", () => toggle(a, suspended));
      li.querySelector('[data-act="del"]').addEventListener("click", () => remove(a.username));
      el.list.appendChild(li);
    });
  }

  /* ------------------------------------------------------------------ */
  /* Actions                                                             */
  /* ------------------------------------------------------------------ */
  function prefillReset(username) {
    el.user.value = username;
    el.pass.value = generatePassword();
    el.pass.focus();
    el.pass.select();
    hint(`كلمة سر جديدة لـ ${username} — اضغط «حفظ الحساب» لتأكيدها.`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function toggle(a, suspended) {
    try {
      await api(`/api/admins/${encodeURIComponent(a.username)}/status`, {
        method: "POST",
        body: JSON.stringify({ status: suspended ? "active" : "suspended" }),
      });
      hint(`${a.username}: ${suspended ? "تم التفعيل" : "تم الإيقاف"}.`, "ok");
      refresh();
    } catch (err) { hint(err.message, "err"); }
  }

  async function remove(username) {
    if (!confirm(`حذف الحساب «${username}» نهائياً؟`)) return;
    try {
      await api(`/api/admins/${encodeURIComponent(username)}`, { method: "DELETE" });
      hint(`تم حذف ${username}.`, "ok");
      refresh();
    } catch (err) { hint(err.message, "err"); }
  }

  async function save() {
    const username = el.user.value.trim();
    const password = el.pass.value;
    if (!username) return hint("أدخل اسم المستخدم.", "err");
    if (password.length < 8) return hint("كلمة السر قصيرة (8 رموز على الأقل).", "err");
    try {
      const data = await api("/api/admins", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      hint(data.created ? `تم إنشاء ${username}. انسخ كلمة السر الآن.`
                        : `تمت إعادة ضبط كلمة سر ${username}. انسخها الآن.`, "ok");
      el.user.value = "";
      refresh();
    } catch (err) { hint(err.message, "err"); }
  }

  async function copyPassword() {
    const value = el.pass.value;
    if (!value) return hint("لا توجد كلمة سر لنسخها.", "err");
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Clipboard API needs a secure context; fall back to a scratch field.
      el.pass.select();
      document.execCommand("copy");
    }
    el.copy.classList.add("is-done");
    setTimeout(() => el.copy.classList.remove("is-done"), 1200);
    hint("تم نسخ كلمة السر.", "ok");
  }

  /* ------------------------------------------------------------------ */
  el.gen.addEventListener("click", () => {
    el.pass.value = generatePassword();
    hint("كلمة سر جديدة — انسخها قبل الحفظ.");
  });
  el.copy.addEventListener("click", copyPassword);
  el.save.addEventListener("click", save);
  el.pass.addEventListener("keydown", (e) => { if (e.key === "Enter") save(); });
  el.user.addEventListener("keydown", (e) => { if (e.key === "Enter") el.pass.focus(); });

  refresh();
})();
