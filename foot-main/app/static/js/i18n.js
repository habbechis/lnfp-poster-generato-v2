/* =========================================================================
   Interface language: Arabic (default) + French.
   Only the UI chrome — menus, dashboard, management panel, buttons — is
   translated. Team names, stadiums, times, competition names and everything
   rendered onto the posters stay in Arabic.
   ========================================================================= */
(() => {
  "use strict";
  const KEY = "lnfp-lang";
  const lang = () => localStorage.getItem(KEY) || "ar";

  // Arabic UI string -> French. Data strings are deliberately absent so they
  // are never translated.
  const DICT = {
    // -- sidebar / menu --
    "القائمة": "Menu",
    "اختيار المسابقة": "Choisir la compétition",
    "لوحة المدراء": "Panneau d'administration",
    "الترتيب": "Classement",
    "النتائج المباشرة": "Résultats en direct",
    "النتائج المباشرة — الرابطة 1": "Résultats en direct — Ligue 1",
    "بطولة الرابطة المحترفة 1": "Championnat de Ligue Professionnelle 1",
    "تتحدّث النتائج تلقائياً أثناء المباريات. المصدر: API-Football.":
      "Les scores se mettent à jour automatiquement pendant les matchs. Source : API-Football.",
    "جلب النتائج": "Récupérer les scores",
    "لصق النتائج (نص)": "Coller les résultats (texte)",
    "لصق التعيينات (نص)": "Coller les désignations (texte)",
    "رفع PDF": "Importer un PDF",
    "الصق نصّ التعيينات أو ارفع ملف PDF — يُستخرج التاريخ والتوقيت والملعب والفريقان تلقائياً. الشرطات «-----» تعني ملعباً غير محدّد.":
      "Collez le texte des désignations ou importez un PDF — la date, l'heure, le stade et les deux équipes sont extraits automatiquement. Les tirets « ----- » signifient un stade non défini.",
    "الصق نصّ التعيينات أولاً.": "Collez d'abord le texte des désignations.",
    "جارٍ قراءة ملف PDF…": "Lecture du PDF…",
    "تعذّر قراءة ملف PDF.": "Impossible de lire le PDF.",
    "لصق الترتيب (نص)": "Coller le classement (texte)",
    "استخراج وتعبئة": "Extraire et remplir",
    "الصق نصّ نتائج الجولة — تُستخرج النتائج وتُختار الفرق من الرموز تلقائياً، ويُعبّأ الترتيب إن وُجد.":
      "Collez le bulletin de la journée — les scores sont extraits, les équipes sélectionnées via leurs sigles, et le classement rempli s'il est présent.",
    "الصق قائمة «CLASSEMENT» — تُملأ النقاط ويُرتَّب الجدول تلقائياً حسب الرموز.":
      "Collez la liste « CLASSEMENT » — les points sont remplis et le tableau trié automatiquement.",
    "جارٍ التحليل…": "Analyse en cours…",
    "عدد المباريات": "Matchs joués",
    "الصق نصّ النتائج أولاً.": "Collez d'abord le texte des résultats.",
    "الصق نصّ الترتيب أولاً.": "Collez d'abord le texte du classement.",
    "لم يُتعرَّف على أي مباراة في النص.": "Aucun match reconnu dans le texte.",
    "لم يُتعرَّف على أي صف ترتيب في النص.": "Aucune ligne de classement reconnue.",
    "تعذّر تحليل النص.": "Impossible d'analyser le texte.",
    "تحديث النتائج": "Actualiser les scores",
    "اضغط «تحديث النتائج» للجلب.":
      "Appuyez sur « Actualiser les scores » pour charger.",
    "اضغط «تحديث» لجلب النتائج (لا تحديث تلقائي حرصاً على رصيد الطلبات). المصدر: API-Football.":
      "Appuyez sur « Actualiser » pour charger les scores (pas de rafraîchissement automatique, pour préserver le quota). Source : API-Football.",
    "تعذّر الاتصال.": "Connexion impossible.",
    "جلب من API": "Récupérer via API",
    "جارٍ التحديث…": "Mise à jour…",
    "غير مُفعّل": "Non activé",
    "تعذّر التحديث": "Échec de mise à jour",
    "لا مباريات مباشرة": "Aucun match en direct",
    "لا نتائج بعد": "Aucun résultat pour l'instant",
    "لا توجد مباريات مباشرة الآن.": "Aucun match en direct pour le moment.",
    "الميزة غير مُفعّلة — أضِف مفتاح API-Football في الإعدادات.":
      "Fonction non activée — ajoutez une clé API-Football dans les réglages.",
    "الميزة غير مُفعّلة — أضِف مفتاح API-Football.":
      "Fonction non activée — ajoutez une clé API-Football.",
    "لا توجد مباريات مطابقة في هذا التاريخ.":
      "Aucun match correspondant à cette date.",
    "تعذّر الاتصال بـ API-Football.": "Impossible de contacter API-Football.",
    "انتهت": "Terminé", "الاستراحة": "Mi-temps", "لم تبدأ": "À venir",
    "مؤجّلة": "Reporté",
    "الأفيشات المحفوظة": "Affiches enregistrées",
    "تحميل الأفيش": "Télécharger l'affiche",
    "المسابقات": "Compétitions",
    "محرّر الأفيش": "Éditeur d'affiche",
    "الوضع": "Thème",
    "نهاري": "Clair",
    "ليلي": "Sombre",
    // -- topbar --
    "مولّد الأفيشات الرسمية": "Générateur d'affiches officielles",
    "الرابطة الوطنية لكرة القدم المحترفة": "Ligue Nationale de Football Professionnel",
    "خروج": "Déconnexion",
    "تبديل الوضع": "Changer le thème",
    "حالة قاعدة البيانات": "État de la base de données",
    "متصل بـ Firebase": "Connecté à Firebase",
    "تخزين محلي": "Stockage local",
    "جارٍ التحقّق…": "Vérification…",
    "جارٍ التحقّق من قاعدة البيانات…": "Vérification de la base de données…",
    "قاعدة البيانات متّصلة — العمليات متاحة":
      "Base connectée — opérations disponibles",
    "قاعدة البيانات غير متّصلة — تخزين محلّي مؤقّت":
      "Base non connectée — stockage local temporaire",
    "العودة للتطبيق": "Retour à l'application",
    // -- dashboard / editor --
    "إعداد الأفيش": "Configuration de l'affiche",
    "اختر الفرق بالاسم أو الشعار، وسيُملأ الملعب والتاريخ تلقائياً.":
      "Choisissez les équipes par nom ou logo ; le stade et la date se remplissent automatiquement.",
    "المسابقة": "Compétition",
    "اختيار المسابقة يغيّر العنوان والشعار — ويمكنك تعديلهما بحرّية.":
      "Choisir la compétition change le titre et le logo — modifiables librement.",
    "نوع الأفيش": "Type d'affiche",
    "تعيينات (مواعيد)": "Désignations (horaires)",
    "نتائج (بالنتيجة)": "Résultats (scores)",
    "في وضع «النتائج» تُدخل نتيجة كل مباراة يدوياً بدل التوقيت.":
      "En mode « Résultats », saisissez le score de chaque match au lieu de l'heure.",
    "عنوان الأفيش": "Titre de l'affiche",
    "تلقائي": "Automatique",
    "يدوي": "Manuel",
    "سيُستعمل عنوان جاهز حسب نوع الأفيش.":
      "Un titre prêt sera utilisé selon le type d'affiche.",
    "خط العنوان": "Police du titre",
    "حجم العنوان": "Taille du titre",
    "شعار المسابقة (أعلى الأفيش)": "Logo de la compétition (haut de l'affiche)",
    "رفع شعار": "Importer un logo",
    "استعادة": "Réinitialiser",
    "تاريخ الجولة": "Date de la journée",
    "المباريات": "Matchs",
    "إضافة مباراة": "Ajouter un match",
    "تحميل الأفيش (PNG)": "Télécharger l'affiche (PNG)",
    "حفظ": "Enregistrer",
    "المحفوظات": "Enregistrements",
    "معاينة مباشرة": "Aperçu en direct",
    "جاهز": "Prêt",
    "اختر الفرق لعرض المعاينة…": "Choisissez les équipes pour l'aperçu…",
    // -- match row --
    "المستقبِل": "Hôte",
    "الضيف": "Visiteur",
    "ضد": "vs",
    "القنوات": "Chaînes",
    "الملعب (تلقائي)": "Stade (auto)",
    "اختر فريقاً": "Choisir une équipe",
    "القنوات الناقلة": "Chaînes de diffusion",
    "حذف": "Supprimer",
    "ترتيب": "Ordre",
    "بحث بالاسم…": "Rechercher par nom…",
    // -- dynamic status / hints (editor) --
    "أضف مباراة": "Ajoutez un match",
    "جارٍ التوليد…": "Génération…",
    "خطأ": "Erreur",
    "تعذّر توليد المعاينة.": "Échec de l'aperçu.",
    "جارٍ التحميل…": "Chargement…",
    "لا توجد أفيشات محفوظة بعد.": "Aucune affiche enregistrée.",
    "تعذّر التحميل.": "Échec du chargement.",
    "تحميل": "Télécharger",
    "أضف مباراة واحدة على الأقل.": "Ajoutez au moins un match.",
    "جارٍ تجهيز الملف بدقة كاملة…": "Préparation du fichier en pleine résolution…",
    "تم تحميل الأفيش بنجاح.": "Affiche téléchargée avec succès.",
    "لا يمكن حفظ أفيش فارغ.": "Impossible d'enregistrer une affiche vide.",
    "تعذّر الحفظ.": "Échec de l'enregistrement.",
    "تم تحديث الشعار.": "Logo mis à jour.",
    "تعذّرت قراءة الملف.": "Lecture du fichier impossible.",
    // -- ranking --
    "ترتيب البطولة": "Classement du championnat",
    "اسحب الصفوف لإعادة الترتيب، وعدّل النقاط، ثم احفظ أو حمّل الأفيش.":
      "Glissez les lignes pour réordonner, modifiez les points, puis enregistrez ou téléchargez.",
    "لعب — تعبئة الكل": "Joués — tout remplir",
    "رتّب حسب النقاط": "Trier par points",
    "تحميل الصفحة الحالية": "Télécharger la page actuelle",
    "تحميل الصفحتين (ZIP)": "Télécharger les deux pages (ZIP)",
    "صفحة 1": "Page 1",
    "صفحة 2": "Page 2",
    "يُصدَّر الترتيب في صفحتين (كل صفحة نصف الفرق) ليبقى واضحاً — حمّل كل صفحة على حدة.":
      "Le classement s'exporte en deux pages (moitié des équipes chacune) — téléchargez chaque page séparément.",
    "تم حفظ الترتيب.": "Classement enregistré.",
    "تم تحميل الصفحة بنجاح.": "Page téléchargée avec succès.",
    "تم تحميل الصفحتين.": "Les deux pages ont été téléchargées.",
    "جارٍ تجهيز الصفحة الحالية…": "Préparation de la page actuelle…",
    "جارٍ تجهيز الصفحتين…": "Préparation des deux pages…",
    // -- management / admin panel --
    "حسابات المدراء": "Comptes administrateurs",
    "مُسجَّل الدخول:": "Connecté :",
    "إحصائيات الحسابات": "Statistiques des comptes",
    "الحسابات": "Comptes",
    "نشِطة": "Actifs",
    "موقوفة": "Suspendus",
    "مدير جديد": "Nouvel administrateur",
    "الاسم": "Nom d'utilisateur",
    "كلمة السر (تُعاد ضبطها إن كان الحساب موجوداً)":
      "Mot de passe (réinitialisé si le compte existe)",
    "نسخ كلمة السر": "Copier le mot de passe",
    "توليد": "Générer",
    "تُخزَّن كلمة السر مشفّرة — انسخها الآن، لن تُعرض مرة أخرى.":
      "Le mot de passe est chiffré — copiez-le maintenant, il ne sera plus affiché.",
    "حفظ الحساب": "Enregistrer le compte",
    "الحسابات الحالية": "Comptes existants",
    "لا توجد حسابات بعد.": "Aucun compte pour l'instant.",
    "إعادة ضبط": "Réinitialiser",
    "تفعيل": "Activer",
    "إيقاف": "Suspendre",
    "نشِط": "Actif",
    "موقوف": "Suspendu",
    "أدخل اسم المستخدم.": "Saisissez un nom d'utilisateur.",
    "كلمة السر قصيرة (8 رموز على الأقل).":
      "Mot de passe trop court (8 caractères minimum).",
    "كلمة سر جديدة — انسخها قبل الحفظ.":
      "Nouveau mot de passe — copiez-le avant d'enregistrer.",
    "لا توجد كلمة سر لنسخها.": "Aucun mot de passe à copier.",
    "تم نسخ كلمة السر.": "Mot de passe copié.",
    "تم التفعيل": "Activé",
    "تم الإيقاف": "Suspendu",
    "أدخل اسم المستخدم.": "Saisissez un nom d'utilisateur.",
    // -- login / landing --
    "تسجيل الدخول": "Connexion",
    "اختر المسابقة": "Choisir la compétition",
    "حدّد البطولة للانطلاق في إعداد أفيش الجولة — يمكنك تغييرها لاحقاً.":
      "Sélectionnez le championnat pour préparer l'affiche de la journée — modifiable plus tard.",
    "هذا الفضاء مخصّص للمستعملين المرخّص لهم. الرجاء تسجيل الدخول للمتابعة.":
      "Cet espace est réservé aux utilisateurs autorisés. Veuillez vous connecter pour continuer.",
    "كلمة السر": "Mot de passe",
    "دخول": "Se connecter",
    "إظهار كلمة السر": "Afficher le mot de passe",
    "إخفاء كلمة السر": "Masquer le mot de passe",
    "اختر المجموعة": "Choisir le groupe",
    "إعداد أفيش الجولة": "Préparer l'affiche de la journée",
    "إنشاء جدول الترتيب ←": "Créer le tableau de classement ←",
    "المسابقات الأخرى (كأس تونس، المسابقات الإفريقية والعربية) متاحة داخل المحرّر.":
      "Les autres compétitions (Coupe de Tunisie, compétitions africaines et arabes) sont disponibles dans l'éditeur.",
    "المجموعة الأولى": "Groupe 1",
    "المجموعة الثانية": "Groupe 2",
    // -- competition names (cards, sidebar chips, dropdown) --
    "بطولة الرابطة المحترفة 1": "Ligue 1 Professionnelle",
    "بطولة الرابطة المحترفة 2": "Ligue 2 Professionnelle",
    "بطولة الرابطة 2 — المجموعة الأولى": "Ligue 2 — Groupe 1",
    "بطولة الرابطة 2 — المجموعة الثانية": "Ligue 2 — Groupe 2",
    // -- ranking headings / labels --
    "الرابطة 1": "Ligue 1",
    "الرابطة 2 — المجموعة 1": "Ligue 2 — Groupe 1",
    "الرابطة 2 — المجموعة 2": "Ligue 2 — Groupe 2",
    "بطولة الرابطة المحترفة 2 — المجموعة الأولى": "Ligue 2 Professionnelle — Groupe 1",
    "بطولة الرابطة المحترفة 2 — المجموعة الثانية": "Ligue 2 Professionnelle — Groupe 2",
    "لعب": "Joués",
    "نقاط": "Points",
    // -- assorted labels & attributes --
    "ليلي": "Sombre",
    "القائمة الجانبية": "Menu latéral",
    "إغلاق": "Fermer",
    "مصدر العنوان": "Source du titre",
    "محرّر الترتيب": "Éditeur de classement",
    "جدول الترتيب": "Tableau de classement",
    "الصفحة": "Page",
    "اسحب لإعادة الترتيب": "Glisser pour réordonner",
    "تعبئة عدد المباريات للجميع": "Remplir les matchs joués pour tous",
    "عدد المباريات": "Matchs joués",
    "النقاط": "Points",
    "نتيجة المستقبِل": "Score de l'hôte",
    "نتيجة الضيف": "Score du visiteur",
    "حالة قاعدة البيانات": "État de la base de données",
    // -- dynamic confirms & hints --
    "تم تحميل الأفيش المحفوظ.": "Affiche enregistrée chargée.",
    "حجم الشعار كبير جداً (الحد 4 ميغا).": "Logo trop volumineux (max 4 Mo).",
    "حذف هذا الأفيش نهائياً؟": "Supprimer définitivement cette affiche ?",
    "استعادة الترتيب إلى القائمة الأصلية بنقاط صفر؟":
      "Réinitialiser le classement à la liste d'origine avec zéro point ?",
  };

  const tr = (s) => DICT[(s || "").trim()];

  // OPTION is translatable (competition names) but the poster title box
  // (a textarea) and script/style content are not.
  const SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1 };

  function translateTextNode(node) {
    const raw = node.nodeValue;
    const key = raw.trim();
    if (!key) return;
    const fr = DICT[key];
    if (fr) node.nodeValue = raw.replace(key, fr);
  }

  function translateElement(root) {
    // Attributes
    const swapAttr = (el, attr) => {
      const v = el.getAttribute(attr);
      const fr = tr(v);
      if (fr) el.setAttribute(attr, fr);
    };
    const withAttr = (sel, attr) =>
      root.querySelectorAll(sel).forEach((el) => swapAttr(el, attr));
    if (root.nodeType === 1) {
      ["placeholder", "title", "aria-label"].forEach((a) => {
        if (root.hasAttribute && root.hasAttribute(a)) swapAttr(root, a);
      });
    }
    withAttr("[placeholder]", "placeholder");
    withAttr("[title]", "title");
    withAttr("[aria-label]", "aria-label");
    // Text nodes
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        const p = n.parentNode;
        if (!p || SKIP[p.nodeName]) return NodeFilter.FILTER_REJECT;
        return n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT
                                  : NodeFilter.FILTER_REJECT;
      },
    });
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(translateTextNode);
  }

  function injectToggle() {
    const host = document.querySelector(".topbar__tools") ||
                 document.querySelector(".landing__bar");
    if (!host || host.querySelector(".lang-toggle")) return;
    const fr = lang() === "fr";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "icon-btn lang-toggle";
    btn.textContent = fr ? "ع" : "FR";
    btn.title = fr ? "العربية" : "Français";
    btn.setAttribute("aria-label", btn.title);
    btn.addEventListener("click", () => {
      localStorage.setItem(KEY, fr ? "ar" : "fr");
      location.reload();
    });
    host.insertBefore(btn, host.firstChild);
  }

  function start() {
    injectToggle();
    if (lang() !== "fr") return;
    document.documentElement.setAttribute("lang", "fr");
    translateElement(document.body);
    // Content added later (match rows, saved lists, admin rows, live badges).
    const obs = new MutationObserver((muts) => {
      muts.forEach((m) => {
        if (m.type === "characterData") { translateTextNode(m.target); return; }
        m.addedNodes.forEach((nd) => {
          if (nd.nodeType === 1) translateElement(nd);
          else if (nd.nodeType === 3) translateTextNode(nd);
        });
      });
    });
    obs.observe(document.body,
                { childList: true, subtree: true, characterData: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
