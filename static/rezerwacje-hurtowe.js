/* Ustawienia rezerwacji B2B: wlasciciel kancelarii, bez dostepu do kluczy partnerow. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const dialog = $("okno-hurtowe");
  const button = $("btn-hurtowe");
  if (!dialog || !button) return;
  const dni = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"];
  const host = $("hurtowe-dni");
  const rows = [];
  dni.forEach((name, i) => {
    const row = document.createElement("div");
    row.className = "hurtowe-dzien";
    row.innerHTML = '<label><input type="checkbox" data-dzien="' + i + '"> ' + name + '</label>' +
      '<input type="time" value="09:00" min="00:00" max="23:30" step="1800" aria-label="Od ' + name + '">' +
      '<span>do</span><input type="time" value="17:00" min="00:00" max="23:30" step="1800" aria-label="Do ' + name + '">';
    const checkbox = row.querySelector("input[type=checkbox]");
    const times = row.querySelectorAll("input[type=time]");
    const refresh = () => times.forEach(t => t.disabled = !checkbox.checked);
    checkbox.addEventListener("change", refresh);
    host.appendChild(row);
    rows.push({checkbox, start: times[0], end: times[1], refresh});
  });
  const message = (text, error = false) => {
    const el = $("hurtowe-komunikat");
    el.textContent = text;
    el.style.color = error ? "var(--alarm)" : "var(--tekst2)";
  };
  const render = p => {
    $("hurtowe-wlaczone").checked = Boolean(p.wlaczone);
    $("hurtowe-klienci").checked = Boolean(p.klienci);
    $("hurtowe-miasto").value = p.miasto || "";
    $("hurtowe-adres").value = p.adres || "";
    $("hurtowe-czas").value = String(p.czas_minut || 60);
    $("hurtowe-wyprzedzenie").value = String(p.wyprzedzenie_godzin || 24);
    $("hurtowe-horyzont").value = String(p.max_dni || 60);
    rows.forEach((r, i) => {
      const godziny = p.godziny?.[String(i)];
      r.checkbox.checked = Array.isArray(godziny);
      r.start.value = godziny?.[0] || "09:00";
      r.end.value = godziny?.[1] || "17:00";
      r.refresh();
    });
  };
  async function open() {
    message("Wczytuję ustawienia...");
    dialog.showModal();
    try {
      const odp = await api("/api/rezerwacje-hurtowe/ustawienia");
      const p = await odp.json();
      if (!odp.ok) throw new Error(p.detail || "Nie udało się pobrać ustawień.");
      render(p);
      message(p.wlaczone ? "Rezerwacje hurtowe są włączone." : "Rezerwacje hurtowe są wyłączone.");
    } catch (e) {
      message(e.message || "Nie udało się pobrać ustawień.", true);
    }
  }
  button.addEventListener("click", open);
  $("hurtowe-zamknij").addEventListener("click", () => dialog.close());
  $("hurtowe-zapisz").addEventListener("click", async () => {
    const godziny = {};
    rows.forEach((r, i) => {
      if (r.checkbox.checked) godziny[String(i)] = [r.start.value, r.end.value];
    });
    const dane = {
      wlaczone: $("hurtowe-wlaczone").checked,
      klienci: $("hurtowe-klienci").checked,
      miasto: $("hurtowe-miasto").value.trim(),
      adres: $("hurtowe-adres").value.trim(),
      godziny,
      czas_minut: Number($("hurtowe-czas").value),
      wyprzedzenie_godzin: Number($("hurtowe-wyprzedzenie").value),
      max_dni: Number($("hurtowe-horyzont").value)
    };
    const save = $("hurtowe-zapisz");
    save.disabled = true;
    message("Zapisuję ustawienia...");
    try {
      const odp = await api("/api/rezerwacje-hurtowe/ustawienia", {
        method: "PUT", headers: {"Content-Type": "application/json"},
        body: JSON.stringify(dane)
      });
      const wynik = await odp.json();
      if (!odp.ok) throw new Error(wynik.detail || "Nie udało się zapisać.");
      render(wynik);
      message(wynik.wlaczone ? "Zapisano. Partnerzy mogą rezerwować wolne terminy." :
        "Zapisano. Rezerwacje hurtowe są wyłączone.");
    } catch (e) {
      message(e.message || "Nie udało się zapisać.", true);
    } finally {
      save.disabled = false;
    }
  });
})();
