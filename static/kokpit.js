/* NotarAI dashboard, integrated with the existing application state and API.
 * No fake case records, no new API calls without user permissions.
 * The original workflow remains the authority for processing and downloads.
 */
(function () {
  "use strict";

  const node = id => document.getElementById(id);
  const state = {cases: [], query:"", filter:"all", all:false, issue:"", loaded:false};

  function icon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg","svg");
    svg.setAttribute("class","kokpit-icon");
    svg.setAttribute("aria-hidden","true");
    const use = document.createElementNS("http://www.w3.org/2000/svg","use");
    use.setAttribute("href","#kokpit-i-" + name);
    svg.appendChild(use);
    return svg;
  }

  function message(text, kind="") {
    const el = node("kokpit-help");
    if (!el) return;
    el.textContent = text;
    el.dataset.kind = kind;
  }

  function status(caseData) {
    const isProject = Number(caseData.etap) === 3;
    return {
      label: isProject ? "Projekt Word" : "Do weryfikacji",
      note: isProject ? "Projekt przygotowany — wymaga kontroli notariusza"
                      : "Odczyt zapisany — sprawdź dane przed sporządzeniem projektu",
      modifier: isProject ? "ready" : "review",
    };
  }

  function filteredCases() {
    return state.cases.filter(s => {
      const project = Number(s.etap) === 3;
      if (state.filter === "projects" && !project) return false;
      if (state.filter === "review" && project) return false;
      const q = state.query.toLocaleLowerCase("pl");
      const haystack = [s.nazwa, s.sygnatura, s.utworzono]
        .filter(Boolean).join(" ").toLocaleLowerCase("pl");
      return !q || haystack.includes(q);
    });
  }

  function renderCases() {
    const list = node("kokpit-sprawy");
    const count = node("kokpit-counter");
    const btnAll = node("kokpit-showall");
    if (!list || !count) return;

    const cases = filteredCases();
    const n = state.cases.length;
    const plural = n === 1 ? " sprawa"
      : (n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14))
        ? " sprawy" : " spraw";
    count.textContent = state.loaded ? n + plural : "Wczytywanie";
    list.replaceChildren();

    if (state.issue) {
      const notice = document.createElement("p");
      notice.className = "kokpit-empty";
      notice.setAttribute("role","status");
      notice.textContent = state.issue;
      list.appendChild(notice);
    } else if (!state.loaded) {
      const loading = document.createElement("p");
      loading.className = "kokpit-empty";
      loading.setAttribute("role","status");
      loading.textContent = "Pobieram sprawy kancelarii…";
      list.appendChild(loading);
    } else if (!cases.length) {
      const empty = document.createElement("p");
      empty.className = "kokpit-empty";
      empty.textContent = state.cases.length
        ? "Brak spraw pasujących do wybranych filtrów."
        : "Nie masz jeszcze żadnej zapisanej sprawy. Zacznij od wgrania wzoru aktu i skanów.";
      list.appendChild(empty);
    } else {
      (state.all ? cases : cases.slice(0,5)).forEach(s => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "kokpit-item";
        const title = String(s.nazwa || s.sygnatura || "Sprawa bez nazwy");
        item.setAttribute("aria-label","Otwórz sprawę: " + title);
        item.title = "Otwórz sprawę i kontynuuj";
        item.addEventListener("click", () => {
          message("Otwieram sprawę…");
          Promise.resolve(wczytajSprawe(s.id)).catch(() => {
            message("Nie udało się otworzyć sprawy. Odśwież listę i spróbuj ponownie.", "error");
          });
        });

        const file = document.createElement("span");
        file.className = "kokpit-fileico";
        file.appendChild(icon("file"));
        item.appendChild(file);

        const content = document.createElement("span");
        content.className = "kokpit-item-title";
        const titleNode = document.createElement("strong");
        titleNode.textContent = title;
        const sub = document.createElement("small");
        const kind = status(s);
        const date = typeof s.utworzono === "string" ? s.utworzono.slice(0,10) : "";
        sub.textContent = (s.sygnatura && s.nazwa ? s.sygnatura + " · " : "")
          + kind.note + (date ? " · " + date : "");
        content.append(titleNode,sub);
        item.appendChild(content);

        const pill = document.createElement("span");
        pill.className = "kokpit-state kokpit-state--" + kind.modifier;
        pill.textContent = kind.label;
        item.appendChild(pill);
        list.appendChild(item);
      });
    }
    if (btnAll) {
      btnAll.hidden = cases.length <= 5;
      btnAll.textContent = state.all ? "Pokaż ostatnie 5" : "Pokaż wszystkie (" + cases.length + ")";
    }
  }

  // Called by the existing rysujListeSpraw() after data was read from
  // /api/sprawy OR from the explicitly selected local folder.
  window.odswiezKokpit = function (cases, issue="") {
    state.cases = Array.isArray(cases) ? cases.filter(x => x && x.id) : [];
    state.issue = String(issue || "");
    state.loaded = true;
    renderCases();
  };

  window.pokazKokpit = function () {
    document.body.classList.add("kokpit-widoczny");
    node("btn-kokpit")?.classList.add("active");
    node("btn-kokpit")?.setAttribute("aria-current","page");
    node("kokpit")?.removeAttribute("hidden");
    message("");
    renderCases();
  };

  window.ukryjKokpit = function () {
    document.body.classList.remove("kokpit-widoczny","kokpit-aside-expanded");
    node("btn-kokpit")?.classList.remove("active");
    node("btn-kokpit")?.removeAttribute("aria-current");
    const toggle = node("btn-kokpit-menu");
    if (toggle) toggle.setAttribute("aria-expanded","false");
  };

  function goNew(openPicker=false) {
    node("btn-nowa").click(); // Existing reset logic is used as-is.
    message("");
    if (openPicker) {
      node("pliki").click(); // Direct user activation, triggers native file picker.
    } else {
      node("polecenie")?.focus();
    }
  }

  function goReview() {
    if (!sprawa || !sprawa.id) {
      message("Wybierz sprawę z listy lub utwórz nową, aby przejść do weryfikacji.", "error");
      return;
    }
    if (najdalej >= 2) {
      pokaz(2);
      return;
    }
    message("Najpierw odczytaj dokumenty w tej sprawie.", "error");
  }

  function goWord() {
    if (!sprawa || !sprawa.id) {
      message("Otwórz sprawę, której projekt chcesz pobrać lub przygotować.", "error");
      return;
    }
    if (najdalej >= 3) {
      // Projekt mógł powstać w tej sesji bez ustawienia sprawa.projekt.
      // Użytkownik wybrał Word, więc uruchamiamy istniejący, autoryzowany download.
      pokaz(3);
      node("btn-pobierz")?.click();
      return;
    }
    if (najdalej >= 2) {
      pokaz(2);
      node("btn-generuj")?.focus();
      return;
    }
    message("Najpierw wykonaj odczyt dokumentów, a następnie sporządź projekt.", "error");
  }

  // Dashboard controls are not decorative: every action navigates to an
  // existing, functional workflow, with its existing validation and permissions.
  node("btn-kokpit")?.addEventListener("click", () => pokaz(0));
  node("btn-kokpit-menu")?.addEventListener("click", () => {
    const expanded = document.body.classList.toggle("kokpit-aside-expanded");
    node("btn-kokpit-menu").setAttribute("aria-expanded",String(expanded));
    node("btn-kokpit-menu").setAttribute("aria-label",expanded ? "Zwiń menu" : "Rozwiń menu");
  });
  node("kokpit-new")?.addEventListener("click", () => goNew());
  node("kokpit-assistant")?.addEventListener("click", () => {
    if (sprawa && sprawa.id && najdalej >= 2) {
      pokaz(2);
      node("msg2")?.focus(); // Real conversation already connected to Bedrock.
    } else {
      pokaz(1);
      node("polecenie")?.focus(); // Real scan-reading form.
    }
  });
  node("kokpit-promo-new")?.addEventListener("click", () => goNew());
  node("kokpit-upload")?.addEventListener("click", () => goNew(true));
  node("kokpit-ai")?.addEventListener("click", () => {
    pokaz(1);
    node("btn-odczytaj")?.focus();
    // No automatic processing: inputs and consent remain in the existing flow.
  });
  node("kokpit-review")?.addEventListener("click", goReview);
  node("kokpit-word")?.addEventListener("click", goWord);
  node("kokpit-search")?.addEventListener("input", event => {
    state.query = event.target.value.trim();
    state.all = false;
    renderCases();
  });
  node("kokpit-filters")?.addEventListener("click", event => {
    const btn = event.target.closest("button[data-filter]");
    if (!btn) return;
    state.filter = btn.dataset.filter;
    state.all = false;
    node("kokpit-filters").querySelectorAll("button[data-filter]").forEach(b => {
      b.setAttribute("aria-pressed",String(b === btn));
    });
    renderCases();
  });
  node("kokpit-showall")?.addEventListener("click", () => {
    state.all = !state.all;
    renderCases();
  });
  node("kokpit-refresh")?.addEventListener("click", async () => {
    message("Odświeżam sprawy…");
    try {
      await rysujListeSpraw(); // API authorization and local-folder mode preserved.
      message(state.issue ? state.issue : "Lista spraw została odświeżona.", state.issue ? "error" : "ok");
    } catch {
      message("Nie udało się pobrać listy spraw.", "error");
    }
  });

  // If initial asynchronous fetch returned before this standalone script loaded,
  // reuse the same in-memory data instead of requesting it again.
  if (typeof sprawyLista !== "undefined" && Array.isArray(sprawyLista) && sprawyLista.length) {
    window.odswiezKokpit(sprawyLista);
  } else {
    renderCases();
  }
  // If the asynchronous application bootstrap finished before this file loaded,
  // restore the compact sidebar and active dashboard navigation state.
  if (node("kokpit") && !node("kokpit").hidden) {
    window.pokazKokpit();
  }
})();
