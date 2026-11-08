(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const state = {key:"", offices:[], office:null, date:"", slot:"", slots:[], bookings:[], editing:null, idem:""};
  const changed = () => { state.idem = ""; };
  const polishToday = () => new Date().toLocaleDateString("sv-SE",{timeZone:"Europe/Warsaw"});
  const show = (id, visible) => { $(id).hidden = !visible; };
  const status = (id, message, kind) => {
    const el = $(id);
    el.textContent = message || "";
    el.className = "status" + (kind ? " " + kind : "");
  };
  const node = (tag, className, value) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (value !== undefined) el.textContent = value;
    return el;
  };
  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", "Bearer " + state.key);
    if (options.body) headers.set("Content-Type", "application/json");
    let response;
    try {
      response = await fetch(path, {...options, headers, cache:"no-store"});
    } catch {
      throw new Error("Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.");
    }
    let data = null;
    try { data = await response.json(); } catch { /* server unavailable */ }
    if (!response.ok) {
      if (response.status === 401) {
        logout();
        throw new Error("Klucz partnera jest nieprawidłowy albo został zablokowany.");
      }
      throw new Error((data && data.detail) ||
        (response.status === 409 ? "Termin nie jest już dostępny. Odśwież wolne godziny." :
          "Nie udało się wykonać operacji (HTTP " + response.status + ")."));
    }
    return data;
  }
  function logout() {
    state.key = "";
    state.offices = [];
    state.office = null;
    state.slot = "";
    state.bookings = [];
    state.editing = null;
    state.idem = "";
    $("partner-token").value = "";
    $("lista-biur").replaceChildren();
    $("sloty").replaceChildren();
    $("rezerwacje").replaceChildren();
    show("panel",false);
    show("logowanie",true);
  }
  $("wyloguj").addEventListener("click", logout);
  $("form-token").addEventListener("submit", async e => {
    e.preventDefault();
    const token = $("partner-token").value.trim();
    if (!token.startsWith("nth_") || token.length < 32) {
      status("biura-stan","Wpisz pełny klucz partnerski.","error");
      $("partner-token").focus();
      return;
    }
    const button = $("btn-polacz");
    button.disabled = true;
    state.key = token;
    try {
      state.offices = await api("/api/hurtowe/kancelarie");
      $("partner-token").value = "";
      show("logowanie",false);
      show("panel",true);
      state.date = polishToday();
      $("dzien").value = state.date;
      $("dzien").min = state.date;
      status("biura-stan",state.offices.length ? "" : "Brak przypisanych kancelarii udostępniających terminy.");
      renderOffices();
    } catch (error) {
      status("biura-stan",error.message,"error");
      state.key = "";
      show("logowanie",true);
      show("panel",false);
      // Show login errors directly on the login screen, not in a hidden panel.
      $("partner-token").setCustomValidity(error.message);
      $("partner-token").reportValidity();
      $("partner-token").setCustomValidity("");
    } finally { button.disabled = false; }
  });
  $("miasto").addEventListener("input",renderOffices);
  function renderOffices() {
    const list = $("lista-biur");
    list.replaceChildren();
    const filter = $("miasto").value.trim().toLocaleLowerCase("pl");
    const offices = state.offices.filter(o=>!filter || (o.miasto||"").toLocaleLowerCase("pl").includes(filter));
    if (!offices.length) list.append(node("p","empty","Brak kancelarii odpowiadających filtrowi."));
    offices.forEach(office => {
      const b = node("button","office");
      b.type = "button";
      if (state.office?.id === office.id) b.classList.add("active");
      b.append(node("strong","",office.nazwa),node("span","",(office.miasto||"") + " · " + (office.adres||"")));
      b.addEventListener("click",() => selectOffice(office));
      list.append(b);
    });
  }
  async function selectOffice(office) {
    state.office = office;
    state.slot = "";
    state.editing = null;
    changed();
    $("wybrane-biuro").textContent = office.nazwa + " · " + office.adres +
      " · spotkanie " + office.czas_minut + " minut";
    show("formularz-rezerwacji",true);
    show("anuluj-przenoszenie",false);
    $("btn-rezerwuj").textContent="Wybierz godzinę, aby zarezerwować";
    $("btn-rezerwuj").disabled = true;
    renderOffices();
    await Promise.all([loadSlots(),loadBookings()]);
  }
  $("dzien").addEventListener("change", () => {
    state.date = $("dzien").value;
    state.slot = "";
    changed();
    loadSlots();
  });
  $("odswiez").addEventListener("click",loadSlots);
  async function loadSlots() {
    if (!state.office) return;
    const officeId = state.office.id;
    const date = $("dzien").value;
    if (!date) return;
    state.slot = "";
    updateReserveButton();
    $("sloty").replaceChildren();
    status("sloty-stan","Sprawdzam wolne godziny…");
    try {
      const result = await api("/api/hurtowe/dostepnosc?kancelaria="+encodeURIComponent(officeId)+
        "&data="+encodeURIComponent(date));
      if (state.office?.id !== officeId || $("dzien").value !== date) return;
      state.slots = result.terminy || [];
      renderSlots();
      status("sloty-stan",state.slots.length ? "" : "Brak wolnych terminów w tym dniu. Wybierz inną datę.");
    } catch (error) {
      if (state.office?.id === officeId) status("sloty-stan",error.message,"error");
    }
  }
  function renderSlots() {
    $("sloty").replaceChildren();
    state.slots.forEach(s => {
      const btn = node("button","slot",s.godzina);
      btn.type = "button";
      btn.setAttribute("aria-pressed",String(state.slot === s.godzina));
      btn.addEventListener("click",() => {
        state.slot=s.godzina;
        changed();
        renderSlots();
        updateReserveButton();
      });
      $("sloty").append(btn);
    });
  }
  function updateReserveButton() {
    const b = $("btn-rezerwuj");
    b.disabled = !state.slot;
    b.textContent = state.editing
      ? (state.slot ? "Potwierdź zmianę na " + state.slot : "Wybierz nową godzinę")
      : (state.slot ? "Rezerwuj wizytę o " + state.slot : "Wybierz godzinę, aby zarezerwować");
  }
  for(const id of ["rodzaj","rodzaj-inny","telefon","uczestnicy","numer-sprawy"])
    $(id).addEventListener("input", changed);
  function toggleOther(){
    const other = $("rodzaj").value === "inne";
    show("wiersz-rodzaj-inny", other);
    $("rodzaj-inny").required = other;
  }
  $("rodzaj").addEventListener("change",toggleOther);
  toggleOther();
  $("form-rezerwacja").addEventListener("submit",async e => {
    e.preventDefault();
    if(!state.office || !state.slot) return;
    const b = $("btn-rezerwuj");
    const editing = state.editing;
    const office = state.office.id;
    const date = $("dzien").value;
    const time = state.slot;
    const message = editing ? "Zmienić termin spotkania na " + date + " " + time + "?" :
      "Potwierdzić rezerwację w " + state.office.nazwa + " na " + date + " " + time + "?";
    if(!window.confirm(message)) return;
    b.disabled = true;
    status("rezerwacja-stan","Zapisuję w kalendarzu kancelarii…");
    try {
      let result;
      if(editing) {
        result = await api("/api/hurtowe/rezerwacje/"+encodeURIComponent(editing)+
          "?kancelaria="+encodeURIComponent(office),{
            method:"PUT",
            body:JSON.stringify({data:date,godzina:time,potwierdzam:true})
          });
      } else {
        if(!state.idem) state.idem = crypto.randomUUID();
        result = await api("/api/hurtowe/rezerwacje",{
          method:"POST",
          body:JSON.stringify({
            kancelaria:office,data:date,godzina:time,rodzaj:$("rodzaj").value,
            uczestnicy:$("uczestnicy").value.trim(),telefon:$("telefon").value.trim(),
            rodzaj_inny:$("rodzaj-inny").value.trim(),
            zewnetrzne_id:$("numer-sprawy").value.trim(),
            idempotency_key:state.idem,potwierdzam:true
          })
        });
      }
      state.idem = "";
      state.editing = null;
      state.slot = "";
      show("anuluj-przenoszenie",false);
      $("form-rezerwacja").reset();
      toggleOther();
      $("btn-rezerwuj").textContent = "Wybierz godzinę, aby zarezerwować";
      status("rezerwacja-stan","Spotkanie potwierdzone. Numer: "+result.id,"success");
      await Promise.all([loadBookings(),loadSlots()]);
    } catch (error) {
      status("rezerwacja-stan",error.message,"error");
      // Same idempotency key stays for a retry if response is lost.
      await loadSlots();
    } finally { updateReserveButton(); }
  });
  async function loadBookings() {
    if(!state.office) return;
    const id = state.office.id;
    status("rezerwacje-stan","Wczytuję Twoje rezerwacje…");
    try {
      const entries = await api("/api/hurtowe/rezerwacje?kancelaria="+encodeURIComponent(id));
      if(state.office?.id!==id) return;
      state.bookings = entries || [];
      renderBookings();
      status("rezerwacje-stan","");
    } catch(error) {
      if(state.office?.id===id) status("rezerwacje-stan",error.message,"error");
    }
  }
  function renderBookings() {
    $("rezerwacje").replaceChildren();
    const entries = state.bookings.slice().sort((a,b)=>
      (b.data+" "+b.godzina).localeCompare(a.data+" "+a.godzina));
    if(!entries.length) {
      $("rezerwacje").append(node("p","empty","Nie masz jeszcze rezerwacji w tej kancelarii."));
      return;
    }
    entries.forEach(w => {
      const card = node("div","booking");
      const title = node("div","when",w.data+" · "+w.godzina+"–"+w.koniec);
      const description = node("div","detail",(w.uczestnicy||"")+" · "+(w.rodzaj||""));
      const info = node("div","detail","Numer: "+w.id+
        (w.zewnetrzne_id ? " · Zlecenie: "+w.zewnetrzne_id : ""));
      card.append(title,description,info);
      if(w.status === "anulowana") {
        card.append(node("div","muted","Anulowana")); 
      } else {
        const buttons = node("div","actions");
        const move = node("button","btn alt small","Przełóż");
        const cancel = node("button","btn warn small","Anuluj");
        move.type=cancel.type="button";
        move.addEventListener("click",() => {
          state.editing = w.id;
          state.slot = "";
          $("dzien").value=w.data;
          $("uczestnicy").value=w.uczestnicy||"";
          $("rodzaj").value=w.rodzaj||"sprzedaż";
          $("rodzaj-inny").value=w.rodzaj_inny||"";
          toggleOther();
          $("telefon").value=w.telefony?.[0]?.numer||"";
          $("numer-sprawy").value=w.zewnetrzne_id||"";
          show("anuluj-przenoszenie",true);
          updateReserveButton();
          status("rezerwacja-stan","Przenoszenie rezerwacji "+w.id+". Wybierz nową godzinę.");
          loadSlots();
          window.scrollTo({top:0,behavior:"smooth"});
        });
        cancel.addEventListener("click", async () => {
          if(!window.confirm("Odwołać spotkanie "+w.data+" o "+w.godzina+"?")) return;
          cancel.disabled=true;
          try {
            await api("/api/hurtowe/rezerwacje/"+encodeURIComponent(w.id)+
              "/anuluj?kancelaria="+encodeURIComponent(state.office.id),{
                method:"POST",body:JSON.stringify({potwierdzam:true})
              });
            status("rezerwacje-stan","Spotkanie anulowane.","success");
            await Promise.all([loadBookings(),loadSlots()]);
          } catch(error) {
            status("rezerwacje-stan",error.message,"error");
            cancel.disabled=false;
          }
        });
        buttons.append(move,cancel);
        card.append(buttons);
      }
      $("rezerwacje").append(card);
    });
  }
  $("anuluj-przenoszenie").addEventListener("click",() => {
    state.editing=null;
    state.slot="";
    $("form-rezerwacja").reset();
    toggleOther();
    show("anuluj-przenoszenie",false);
    updateReserveButton();
    renderSlots();
    status("rezerwacja-stan","");
  });
})();
