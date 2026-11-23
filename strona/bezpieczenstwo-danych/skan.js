'use strict';
/*
 * Skan bezpieczeństwa kancelarii — silnik detekcji po stronie przeglądarki.
 *
 * ZASADY (RODO + skill strona-premium):
 *  - Zero żądań do obcych serwerów. Jedyne wywołania sieciowe idą do
 *    https://app.notarai.pl/api/skan/* (nasz backend) i są opcjonalne:
 *    strona działa w pełni bez nich.
 *  - Nic nie jest "przejmowane". Czytamy wyłącznie to, co przeglądarka sama
 *    udostępnia każdej stronie (user agent, strefa czasowa, ekran) — i wprost
 *    to mówimy. Hasło w teście wycieku NIGDY nie opuszcza przeglądarki:
 *    liczymy lokalnie SHA-1 i wysyłamy tylko 5 pierwszych znaków skrótu
 *    (model k-anonimowości Have I Been Pwned).
 *  - Żadnych danych osobowych w logach ani w telemetrii.
 *
 * Werdykty: 'ok' (zielony) | 'uwaga' (bursztyn) | 'alarm' (czerwony) | 'info'.
 */

const API = 'https://app.notarai.pl';

/* Fakty o końcu wsparcia i minimalne bezpieczne wersje przeglądarek.
 * Zamrożone na dzień budowy strony — aktualizować przy zmianach. */
const DANE = {
  zbudowano: '2026-11-23',
  // Koniec wsparcia systemów Windows (źródło: Microsoft Lifecycle).
  windows: {
    '6.1': { nazwa: 'Windows 7', wsparcieDo: '2020-01-14' },
    '6.2': { nazwa: 'Windows 8', wsparcieDo: '2016-01-12' },
    '6.3': { nazwa: 'Windows 8.1', wsparcieDo: '2023-01-10' },
    // NT 10.0 to Windows 10 albo 11 — rozróżniamy po platformVersion (UA-CH).
    win10: { nazwa: 'Windows 10', wsparcieDo: '2025-10-14' },
    win11: { nazwa: 'Windows 11', wsparcieDo: null },
  },
  // Minimalne wersje główne, które jeszcze dostają poprawki bezpieczeństwa.
  // Konserwatywne progi: poniżej = na pewno przestarzała.
  przegladarki: { Chrome: 120, Edge: 120, Firefox: 115, Opera: 106 },
};

const dzisiaj = () => new Date();

function czyPoWsparciu(dataISO) {
  if (!dataISO) return false;
  return dzisiaj() > new Date(dataISO + 'T23:59:59');
}
function latNiedlugo(dataISO) {
  const dni = Math.floor((dzisiaj() - new Date(dataISO)) / 86400000);
  if (dni < 0) return 'za ' + Math.abs(Math.round(dni / 30)) + ' mies.';
  const lata = dni / 365;
  return lata >= 1 ? 'od ' + lata.toFixed(1).replace('.', ',') + ' roku' : 'od ' + Math.round(dni / 30) + ' mies.';
}

/* ---------- System operacyjny ---------- */
async function wykryjSystem() {
  const ua = navigator.userAgent || '';
  let platformVersion = null;
  try {
    if (navigator.userAgentData && navigator.userAgentData.getHighEntropyValues) {
      const v = await navigator.userAgentData.getHighEntropyValues(['platformVersion']);
      platformVersion = v && v.platformVersion ? v.platformVersion : null;
    }
  } catch (_) { /* brak UA-CH — trudno, lecimy dalej */ }

  // Windows?
  const mNT = ua.match(/Windows NT ([\d.]+)/);
  if (mNT) {
    const nt = mNT[1];
    if (DANE.windows[nt]) {
      const w = DANE.windows[nt];
      return werdyktSystem(w.nazwa, w.wsparcieDo, true);
    }
    if (nt === '10.0') {
      // Windows 10 vs 11 — UA-CH platformVersion: major >= 13 => Windows 11.
      let win = DANE.windows.win10;
      let pewne = false;
      if (platformVersion) {
        const major = parseInt(platformVersion.split('.')[0], 10);
        if (!isNaN(major)) { pewne = true; win = major >= 13 ? DANE.windows.win11 : DANE.windows.win10; }
      }
      return werdyktSystem(win.nazwa, win.wsparcieDo, pewne);
    }
    return { klucz: 'system', tytul: 'System Windows', werdykt: 'info',
      opis: 'Wykryto Windows, ale przeglądarka nie podaje dokładnej wersji.' };
  }
  // Inne systemy — informacyjnie, bez straszenia.
  if (/Mac OS X|Macintosh/.test(ua)) return { klucz: 'system', tytul: 'System: macOS', werdykt: 'info',
    opis: 'Sprawdź w Ustawieniach, czy masz najnowszą obsługiwaną wersję macOS i czy włączone jest FileVault (szyfrowanie dysku).' };
  if (/Android/.test(ua)) return { klucz: 'system', tytul: 'System: Android', werdykt: 'info',
    opis: 'Do pracy z aktami zalecamy komputer kancelarii, nie telefon.' };
  if (/Linux|X11/.test(ua)) return { klucz: 'system', tytul: 'System: Linux', werdykt: 'info',
    opis: 'Upewnij się, że dystrybucja dostaje aktualizacje bezpieczeństwa i że dysk jest zaszyfrowany (LUKS).' };
  return { klucz: 'system', tytul: 'System operacyjny', werdykt: 'info', opis: 'Nie rozpoznano systemu z danych przeglądarki.' };
}
function werdyktSystem(nazwa, wsparcieDo, pewne) {
  const prefiks = pewne ? '' : 'Prawdopodobnie ';
  if (wsparcieDo && czyPoWsparciu(wsparcieDo)) {
    const d = new Date(wsparcieDo).toLocaleDateString('pl-PL');
    return { klucz: 'system', tytul: prefiks + nazwa, werdykt: 'alarm', wsparcieDo: wsparcieDo,
      opis: 'Ten system nie dostaje już poprawek bezpieczeństwa (wsparcie zakończyło się ' + d + ', ' + latNiedlugo(wsparcieDo) + ' temu). Każda nowa luka w Windowsie zostaje w nim na zawsze — to najpoważniejsze ryzyko dla danych w kancelarii.',
      czyn: 'Przejście na obsługiwany Windows 11 (lub ESU jako doraźny bufor).' };
  }
  if (wsparcieDo) {
    const miesDo = Math.round((new Date(wsparcieDo) - dzisiaj()) / (86400000 * 30));
    if (miesDo <= 12) return { klucz: 'system', tytul: prefiks + nazwa, werdykt: 'uwaga',
      opis: 'Wsparcie kończy się ' + new Date(wsparcieDo).toLocaleDateString('pl-PL') + ' (za ok. ' + miesDo + ' mies.). Warto zaplanować migrację zawczasu.' };
  }
  return { klucz: 'system', tytul: prefiks + nazwa, werdykt: 'ok',
    opis: 'System jest wspierany i dostaje poprawki bezpieczeństwa. To dobra podstawa — reszta zależy od konfiguracji (szyfrowanie, kopie, aktualizacje).' };
}

/* ---------- Przeglądarka ---------- */
function wykryjPrzegladarke() {
  const ua = navigator.userAgent || '';
  let nazwa = null, wersja = null;
  const brands = navigator.userAgentData && navigator.userAgentData.brands;
  if (Array.isArray(brands)) {
    for (const b of brands) {
      if (/Edge/i.test(b.brand)) { nazwa = 'Edge'; wersja = parseInt(b.version, 10); }
      else if (/Opera|OPR/i.test(b.brand)) { nazwa = 'Opera'; wersja = parseInt(b.version, 10); }
      else if (/Google Chrome/i.test(b.brand) && nazwa !== 'Edge') { nazwa = 'Chrome'; wersja = parseInt(b.version, 10); }
    }
  }
  if (!nazwa) {
    let m;
    if ((m = ua.match(/Edg\/(\d+)/))) { nazwa = 'Edge'; wersja = +m[1]; }
    else if ((m = ua.match(/OPR\/(\d+)/))) { nazwa = 'Opera'; wersja = +m[1]; }
    else if ((m = ua.match(/Firefox\/(\d+)/))) { nazwa = 'Firefox'; wersja = +m[1]; }
    else if ((m = ua.match(/Chrome\/(\d+)/))) { nazwa = 'Chrome'; wersja = +m[1]; }
    else if (/Safari/.test(ua) && (m = ua.match(/Version\/(\d+)/))) { nazwa = 'Safari'; wersja = +m[1]; }
    else if ((m = ua.match(/MSIE (\d+)|Trident/))) { nazwa = 'Internet Explorer'; wersja = m[1] ? +m[1] : 11; }
  }
  if (nazwa === 'Internet Explorer') return { klucz: 'przegladarka', tytul: 'Internet Explorer', werdykt: 'alarm',
    opis: 'Internet Explorer nie jest już rozwijany ani wspierany. To jedna z najłatwiejszych dróg włamania. Przejdź na aktualny Edge lub Chrome.',
    czyn: 'Zmiana przeglądarki na aktualną.' };
  if (!nazwa || !wersja) return { klucz: 'przegladarka', tytul: 'Przeglądarka', werdykt: 'info',
    opis: 'Nie udało się rozpoznać wersji. Upewnij się, że masz włączone automatyczne aktualizacje.' };
  const prog = DANE.przegladarki[nazwa];
  if (prog && wersja < prog) return { klucz: 'przegladarka', tytul: nazwa + ' ' + wersja, werdykt: 'alarm',
    opis: 'Ta wersja jest przestarzała (bezpieczne minimum to ' + prog + '+). Przestarzała przeglądarka to otwarte drzwi — aktualizacje łatają realnie wykorzystywane luki.',
    czyn: 'Aktualizacja przeglądarki i włączenie automatycznych aktualizacji.' };
  return { klucz: 'przegladarka', tytul: nazwa + ' ' + wersja, werdykt: 'ok',
    opis: 'Wersja wygląda na aktualną. Trzymaj włączone automatyczne aktualizacje, żeby tak zostało.' };
}

/* ---------- Połączenie ---------- */
function wykryjPolaczenie() {
  const https = location.protocol === 'https:';
  const bezpiecznyKontekst = typeof isSecureContext !== 'undefined' ? isSecureContext : https;
  if (!https) return { klucz: 'polaczenie', tytul: 'Połączenie nieszyfrowane', werdykt: 'alarm',
    opis: 'Ta strona nie jest otwarta po HTTPS. Dane mogą być podsłuchane w sieci.' };
  return { klucz: 'polaczenie', tytul: 'Połączenie szyfrowane (HTTPS)', werdykt: 'ok',
    opis: 'Połączenie z tą stroną jest szyfrowane' + (bezpiecznyKontekst ? '' : '') + '. To dobrze — ale szyfrowanie strony nie chroni plików na Twoim dysku ani poczty. Tym zajmują się kolejne punkty.' };
}

/* ---------- Co widzą o Tobie strony (fingerprint) ---------- */
function wykryjSlad() {
  const d = [];
  try { d.push(['Strefa czasowa', Intl.DateTimeFormat().resolvedOptions().timeZone]); } catch (_) {}
  d.push(['Język', (navigator.languages && navigator.languages.join(', ')) || navigator.language || '—']);
  d.push(['Ekran', screen.width + '×' + screen.height + ' px, ' + (window.devicePixelRatio || 1) + '×']);
  if (navigator.hardwareConcurrency) d.push(['Rdzenie procesora', String(navigator.hardwareConcurrency)]);
  if (navigator.deviceMemory) d.push(['Pamięć (ok.)', navigator.deviceMemory + ' GB']);
  d.push(['Dotyk', (navigator.maxTouchPoints || 0) > 0 ? 'tak' : 'nie']);
  return { klucz: 'slad', tytul: 'To widzi o Tobie każda strona', werdykt: 'info', dane: d,
    opis: 'Te informacje każda odwiedzana strona odczytuje automatycznie, bez pytania o zgodę — tak działa przeglądarka. Pojedynczo nieszkodliwe, ale razem tworzą „odcisk palca”, po którym da się Cię śledzić między stronami.' };
}

/* ---------- Publiczny IP (opcjonalnie, nasz backend) ---------- */
async function wykryjIP() {
  try {
    const r = await fetch(API + '/api/skan/ip', { headers: { 'Accept': 'application/json' } });
    if (!r.ok) return null;
    const j = await r.json().catch(() => null);
    if (!j || !j.ip) return null;
    const miejsce = [j.miasto, j.kraj].filter(Boolean).join(', ');
    return { klucz: 'ip', tytul: 'Twój adres widoczny z internetu', werdykt: 'info',
      dane: [['Adres IP', j.ip]].concat(miejsce ? [['Przybliżona lokalizacja', miejsce]] : []),
      opis: 'Tyle widzi o Twoim łączu każdy serwer, z którym się łączysz. To normalne — pokazujemy, żeby było jasne, że „anonimowości w sieci” nie ma z automatu.' };
  } catch (_) { return null; }
}

/* ---------- Hasło: test wycieku (HIBP, k-anonimowość) ---------- */
async function sha1Hex(tekst) {
  const bufor = new TextEncoder().encode(tekst);
  const hash = await crypto.subtle.digest('SHA-1', bufor);
  return [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('').toUpperCase();
}
async function sprawdzHaslo(haslo) {
  if (!haslo) return null;
  if (!(window.crypto && crypto.subtle)) return { blad: 'Ta przeglądarka nie pozwala bezpiecznie sprawdzić hasła.' };
  const hash = await sha1Hex(haslo);
  const prefiks = hash.slice(0, 5), reszta = hash.slice(5);
  // Do backendu idzie TYLKO 5 pierwszych znaków skrótu — nie hasło.
  const r = await fetch(API + '/api/skan/hibp-haslo?prefiks=' + prefiks, { headers: { 'Accept': 'text/plain' } });
  if (!r.ok) throw new Error('Nie udało się połączyć z usługą sprawdzania.');
  const tekst = await r.text();
  let ile = 0;
  for (const linia of tekst.split('\n')) {
    const [suf, licz] = linia.trim().split(':');
    if (suf && suf.toUpperCase() === reszta) { ile = parseInt(licz, 10) || 0; break; }
  }
  if (ile > 0) return { ile, werdykt: 'alarm',
    opis: 'To hasło pojawiło się w znanych wyciekach danych ' + ile.toLocaleString('pl-PL') + ' razy. Jest na listach, których używają włamywacze — zmień je wszędzie, gdzie go używasz, i nie używaj ponownie.' };
  return { ile: 0, werdykt: 'ok',
    opis: 'Tego hasła nie ma w znanych wyciekach. To dobry znak, ale nie gwarancja — liczy się też długość, unikalność i menedżer haseł.' };
}

/* ---------- Samoaudyt: rzeczy, których przeglądarka nie zobaczy ---------- */
const SAMOAUDYT = [
  { id: 'szyfrowanie', pytanie: 'Dysk komputera jest zaszyfrowany (BitLocker / FileVault)?',
    gdyNie: 'Bez szyfrowania każdy, kto fizycznie weźmie komputer lub dysk, odczyta wszystkie akta. To podstawa ochrony danych w kancelarii.', waga: 20,
    jak: ['Ustawienia → Prywatność i zabezpieczenia → Szyfrowanie urządzenia (lub „Szyfrowanie dysków BitLocker”).',
      'Włącz i poczekaj, aż dysk się zaszyfruje.',
      'KONIECZNIE zapisz lub wydrukuj klucz odzyskiwania i schowaj go do sejfu — bez niego nikt (także Ty) nie odzyska danych.',
      'Windows Home: poszukaj „Szyfrowanie urządzenia”; jeśli go nie ma — rozważ sprawdzony VeraCrypt.'] },
  { id: 'kopie', pytanie: 'Masz regularne kopie zapasowe (poza tym komputerem)?',
    gdyNie: 'Bez kopii jeden ransomware albo awaria dysku to utrata akt. Kopia musi być odłączona albo w chmurze w UE.', waga: 18,
    jak: ['Podłącz dysk zewnętrzny albo włącz kopię w chmurze w UE.',
      'Ustaw kopię automatyczną (Historia plików / kopia w chmurze), nie „raz na kiedyś”.',
      'Trzymaj przynajmniej jedną kopię ODŁĄCZONĄ od komputera (offline) — ransomware nie zaszyfruje tego, czego nie dosięgnie.',
      'Raz na jakiś czas sprawdź, że naprawdę da się z niej odtworzyć plik.'] },
  { id: 'aktualizacje', pytanie: 'Windows pobiera i instaluje aktualizacje na bieżąco?',
    gdyNie: 'Zaległe poprawki to główna droga wejścia ransomware i włamań. Zalecamy (nie wymuszamy) regularne aktualizacje.', waga: 12,
    ustawienia: 'ms-settings:windowsupdate', ustawieniaTekst: 'Otwórz Windows Update',
    jak: ['Ustawienia → Windows Update → „Sprawdź aktualizacje” i zainstaluj wszystkie.',
      'Włącz pobieranie aktualizacji automatycznie.',
      'Rób to regularnie — to sugestia, nie przymus, ale to jedna z najważniejszych rzeczy.',
      'Jeśli masz Windows 10 po końcu wsparcia, aktualizacje już nie przyjdą — rozważ przejście na Windows 11.'] },
  { id: 'antywirus', pytanie: 'Masz aktywną i aktualną ochronę antywirusową?',
    gdyNie: 'Włącz przynajmniej Microsoft Defender i upewnij się, że jest aktualny.', waga: 12,
    ustawienia: 'ms-settings:windowsdefender', ustawieniaTekst: 'Otwórz Zabezpieczenia Windows',
    jak: ['Otwórz „Zabezpieczenia Windows” → Ochrona przed wirusami i zagrożeniami.',
      'Upewnij się, że ochrona w czasie rzeczywistym jest włączona i aktualna.',
      'Uruchom szybki skan.'] },
  { id: 'blokada', pytanie: 'Komputer blokuje się sam i wymaga hasła po odejściu?',
    gdyNie: 'Niezablokowany komputer to dostęp do akt dla każdego, kto przejdzie obok biurka.', waga: 10,
    ustawienia: 'ms-settings:signinoptions', ustawieniaTekst: 'Otwórz Opcje logowania',
    jak: ['Ustawienia → Konta → Opcje logowania → „Wymagaj logowania” po wybudzeniu/uśpieniu.',
      'Ustawienia → System → Zasilanie → krótki czas do uśpienia ekranu.',
      'Skrót: Windows + L blokuje ekran od razu, gdy wstajesz od biurka.'] },
  { id: 'mfa', pytanie: 'Poczta kancelarii ma włączone logowanie dwuskładnikowe (2FA)?',
    gdyNie: 'Samo hasło do poczty nie wystarcza — to przez pocztę najczęściej przejmuje się dostęp. Włącz 2FA.', waga: 15,
    jak: ['Wejdź w ustawienia bezpieczeństwa swojej poczty (nazwa zależy od dostawcy).',
      'Włącz „Weryfikację dwuetapową / logowanie dwuskładnikowe (2FA)”.',
      'Użyj aplikacji typu Authenticator — jest pewniejsza niż kod SMS.'] },
  { id: 'menedzer', pytanie: 'Używasz menedżera haseł (różne hasła do różnych usług)?',
    gdyNie: 'Powtarzane hasła to efekt domina: jeden wyciek otwiera wszystko. Menedżer haseł to rozwiązuje.', waga: 10,
    jak: ['Wybierz menedżer haseł (wbudowany w przeglądarkę albo osobny).',
      'Pozwól mu generować różne, długie hasła do każdej usługi.',
      'Włącz autouzupełnianie i przestań trzymać hasła w głowie czy na kartce.'] },
];

/* ---------- Wynik łączny ---------- */
function policzWynik(karty, samoaudyt) {
  // Start 100, odejmujemy kary. Technika z przeglądarki + deklaracje z samoaudytu.
  let pkt = 100;
  const kary = { alarm: 22, uwaga: 10 };
  for (const k of karty) if (kary[k.werdykt]) pkt -= kary[k.werdykt];
  for (const poz of SAMOAUDYT) if (samoaudyt[poz.id] === false) pkt -= poz.waga;
  pkt = Math.max(3, Math.min(100, Math.round(pkt)));
  let poziom, naglowek;
  if (pkt >= 80) { poziom = 'ok'; naglowek = 'Solidnie — ale jest co dopiąć'; }
  else if (pkt >= 55) { poziom = 'uwaga'; naglowek = 'Są poważne luki do zamknięcia'; }
  else { poziom = 'alarm'; naglowek = 'Dane Twojej kancelarii są realnie zagrożone'; }
  return { pkt, poziom, naglowek };
}

/* Maskowanie hasła, które użytkownik SAM wpisał do sprawdzenia — pokazujemy
 * je w większości wygwiazdkowane, żeby rozpoznał, że to jego, ale żeby nie
 * wyświetlać go w całości. Liczba kropek = realna długość (krótkie = widać). */
function maskujHaslo(h) {
  const n = h.length;
  if (n <= 2) return '•'.repeat(Math.max(n, 1));
  if (n <= 5) return h[0] + '•'.repeat(n - 1);
  return h[0] + h[1] + '•'.repeat(n - 3) + h[n - 1];
}

/* Szczera, lokalna ocena siły hasła (bez bibliotek, bez wysyłki).
 * Zwraca { poziom, etykieta, opis } — celowo dosadna przy słabych. */
const SLABE = ['haslo','hasło','password','qwerty','123456','12345678','111111','zaq12wsx','iloveyou','admin','polska','notariusz','kancelaria','1qaz2wsx','000000','abc123','password1'];
function ocenSile(h) {
  const n = h.length;
  const male = /[a-ząćęłńóśźż]/.test(h), duze = /[A-ZĄĆĘŁŃÓŚŹŻ]/.test(h);
  const cyfry = /\d/.test(h), znaki = /[^A-Za-z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/.test(h);
  const klasy = [male, duze, cyfry, znaki].filter(Boolean).length;
  const dolne = h.toLowerCase();
  const trywialne = SLABE.some(s => dolne.includes(s)) || /^\d+$/.test(h) || /^(.)\1+$/.test(h) ||
    /0123|1234|2345|3456|4567|5678|6789|abcd|qwer/.test(dolne);
  if (trywialne || n < 6)
    return { poziom: 'alarm', etykieta: 'Banalne', opis: 'To hasło łamie się w kilka sekund — jest krótkie lub oparte na schemacie, który łamacze haseł sprawdzają w pierwszej kolejności.' };
  if (n < 10 || klasy <= 2)
    return { poziom: 'uwaga', etykieta: 'Słabe', opis: 'To hasło da się złamać szybciej, niż myślisz (od minut do godzin). Zbyt krótkie albo zbyt przewidywalne — dołóż długości i różnych znaków, a najlepiej użyj menedżera haseł.' };
  if (n >= 14 && klasy >= 3)
    return { poziom: 'ok', etykieta: 'Mocne', opis: 'Długie i zróżnicowane — to dobra droga. Pod warunkiem, że używasz go tylko w jednym miejscu.' };
  return { poziom: 'uwaga', etykieta: 'Przeciętne', opis: 'Niezłe, ale można lepiej: 14+ znaków i kilka rodzajów znaków. Przede wszystkim nie używaj go w więcej niż jednym serwisie.' };
}

/* ---------- Odsłonięcie na realne scenariusze zagrożeń ----------
 * Z przeglądarki NIE wykryjemy ransomware ani intruza na żywo. Ale uczciwie
 * pokazujemy ODSŁONIĘCIE: „jesteś otwarty na X, bo [wykryte czynniki]".
 * Liczymy z techniki (karty) i z samoaudytu (deklaracje). Żadnego udawania,
 * że coś „wykryto" — mówimy o ryzyku wynikającym z konkretnych braków. */
function ocenZagrozenia(karty, samoaudyt) {
  const wer = {}; for (const k of karty) wer[k.klucz] = k.werdykt;
  const alarm = klucz => wer[klucz] === 'alarm';
  const slaby = klucz => wer[klucz] === 'alarm' || wer[klucz] === 'uwaga';
  const nie = id => samoaudyt[id] === false;
  const band = { alarm: 'wysoka', uwaga: 'średnia', ok: 'niska' };

  function scenariusz(nazwa, typ, konsekwencja, rozwiazanie, czynniki) {
    const aktywne = czynniki.filter(c => c.zly);
    let poziom = aktywne.length >= 2 ? 'alarm' : aktywne.length === 1 ? 'uwaga' : 'ok';
    if (aktywne.some(c => c.krytyczny)) poziom = 'alarm';
    return { nazwa, typ, konsekwencja, rozwiazanie, poziom, powody: aktywne.map(c => c.tekst),
      latwosc: band[poziom], skutecznosc: band[poziom] };
  }

  return [
    scenariusz(
      'Ransomware zaszyfruje Twoje akta',
      'Złośliwe oprogramowanie szyfruje dysk — najczęściej z załącznika, linku albo przez niezałataną lukę w systemie. Działa automatycznie, masowo, nie wybiera „ważnych” ofiar.',
      'Akta wszystkich spraw zablokowane do odwołania, żądanie okupu (zwykle w kryptowalucie), zgłoszenie do UODO w 72 godziny, zawiadomienie klientów i ryzyko odpowiedzialności dyscyplinarnej. Bez kopii — akta przepadają bezpowrotnie.',
      [
        'Szyfrowane, certyfikowane kopie zapasowe w UE — masz z czego odtworzyć akta, więc okup przestaje mieć sens.',
        'Aktualny, wspierany system i oprogramowanie — koniec z dziurami, na które nie ma łatki.',
        'Monitoring i ochrona antywirusowa w standardzie.',
      ],
      [
        { zly: alarm('system'), krytyczny: true, tekst: 'nieaktualny system bez poprawek — główna, zautomatyzowana droga ransomware' },
        { zly: nie('kopie'), krytyczny: true, tekst: 'brak kopii zapasowych poza komputerem — nie ma z czego odtworzyć akt' },
        { zly: slaby('przegladarka'), tekst: 'przestarzała przeglądarka — wejście przez zwykłą stronę' },
        { zly: nie('antywirus'), tekst: 'brak aktywnej ochrony antywirusowej' },
      ]),
    scenariusz(
      'Ktoś przejmie Twoją pocztę i konta (phishing)',
      'Fałszywy e-mail lub podrobiona strona logowania wyłudza hasło; gotowe, wykradzione wcześniej hasła sprawdza się automatycznie w tysiącach usług (credential stuffing).',
      'Z przejętej poczty atakujący podszywa się pod Ciebie wobec klientów i urzędów, resetuje hasła do innych usług, zmienia numery kont do przelewów i sięga po dane oraz pieniądze.',
      [
        'Logowanie dwuskładnikowe (2FA) wszędzie, gdzie wchodzą dane kancelarii — samo hasło przestaje wystarczać atakującemu.',
        'Menedżer haseł — koniec z powtarzaniem haseł, które wyciekają.',
        'Algorytmiczna minimalizacja i maskowanie danych w naszych narzędziach — wysyłamy jak najmniej i bez danych wrażliwych.',
      ],
      [
        { zly: alarm('haslo'), krytyczny: true, tekst: 'Twoje hasło jest w znanych wyciekach — atakujący ma je gotowe' },
        { zly: wer['haslo'] === 'uwaga', tekst: 'słabe hasło — szybkie do złamania' },
        { zly: nie('mfa'), krytyczny: true, tekst: 'brak logowania dwuskładnikowego (2FA) — samo hasło wystarcza' },
        { zly: nie('menedzer'), tekst: 'powtarzane hasła — jeden wyciek otwiera wszystko' },
      ]),
    scenariusz(
      'Ktoś wejdzie na Twój komputer i wykradnie dane',
      'Zdalny dostęp przez niezałataną lukę albo fizyczny — kradzież lub zguba sprzętu z nieszyfrowanym dyskiem. W obu przypadkach dane leżą otworem.',
      'Dostęp do wszystkich akt i danych klientów (PESEL, adresy, majątek). Przy kradzieży lub zgubie laptopa — odczyt całego dysku bez żadnej przeszkody, a Ty nawet nie wiesz, że dane wyciekły.',
      [
        'Szyfrowanie dysków (BitLocker) — skradziony komputer to bezużyteczna cegła, nie skarbnica akt.',
        'Automatyczna blokada ekranu i kontrola dostępu do stanowiska.',
        'Infrastruktura jednego z największych dostawców (AWS), region UE (eu-central-1), ośrodki certyfikowane ISO 27001 i SOC 2.',
      ],
      [
        { zly: alarm('system'), krytyczny: true, tekst: 'nieaktualny system z publicznie znanymi lukami' },
        { zly: nie('szyfrowanie'), krytyczny: true, tekst: 'dysk niezaszyfrowany — kto weźmie komputer, czyta akta' },
        { zly: nie('blokada'), tekst: 'komputer nie blokuje się po odejściu od biurka' },
        { zly: nie('antywirus'), tekst: 'brak aktywnej ochrony antywirusowej' },
      ]),
  ];
}

/* Odczyt sprzętu bez żadnej zgody — karta graficzna przez WebGL. To jedno
 * z najmocniejszych „wiemy o Tobie dużo": model GPU widać bez pytania. */
function czytajGPU() {
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
    if (!gl) return null;
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    if (!ext) return null;
    let r = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) || null;
    if (r) r = String(r).replace(/^ANGLE \(/, '').replace(/\)$/, '').replace(/ \(0x[0-9A-Fa-f]+\)/g, '');
    return r;
  } catch (_) { return null; }
}

/* Znane, publicznie udokumentowane luki Windowsa — jako ILUSTRACJA ścieżki
 * ataku, nie jako „wykryto u Ciebie". Pokazujemy je dla systemu PO końcu
 * wsparcia: uczciwa teza brzmi „na żadną kolejną taką lukę nie dostaniesz
 * już łatki". Zero instrukcji ataku — tylko nazwa, czego dotyczy i co otwiera. */
// Klasyki — timeless ilustracje ścieżki ataku, dostępne też offline (fallback).
// Świeże, aktywnie wykorzystywane luki przychodzą na żywo z backendu (CISA KEV).
const LUKI_WINDOWS = [
  { id: 'CVE-2017-0144', nazwa: 'EternalBlue (SMB)', co: 'luka w udostępnianiu plików',
    naPozwala: 'zdalne uruchomienie kodu bez żadnej akcji użytkownika — tak rozsiał się ransomware WannaCry', aktywna: false,
    url: 'https://nvd.nist.gov/vuln/detail/CVE-2017-0144' },
  { id: 'CVE-2019-0708', nazwa: 'BlueKeep (RDP)', co: 'luka w pulpicie zdalnym',
    naPozwala: 'zdalne przejęcie komputera bez hasła; robak sam przeskakuje na kolejne maszyny w sieci', aktywna: false,
    url: 'https://nvd.nist.gov/vuln/detail/CVE-2019-0708' },
  { id: 'CVE-2021-34527', nazwa: 'PrintNightmare (druk)', co: 'luka w usłudze drukowania',
    naPozwala: 'zdobycie uprawnień administratora i uruchomienie dowolnego programu', aktywna: false,
    url: 'https://nvd.nist.gov/vuln/detail/CVE-2021-34527' },
];
function znaneLuki(sys) {
  if (!sys || sys.werdykt !== 'alarm') return null;   // sens tylko po końcu wsparcia
  return {
    wstep: 'To realne, udokumentowane luki Windowsa — każdą sprawdzisz w oficjalnym wpisie (link). Które z nich są akurat u Ciebie otwarte, zależy od poziomu aktualizacji; ale Twój system po końcu wsparcia na żadną kolejną nie dostanie już łatki. „Aktywnie wykorzystywana” to luki używane w atakach teraz (źródło: katalog CISA, odświeżany automatycznie).',
    luki: LUKI_WINDOWS,
  };
}

/* Świeże, aktywnie wykorzystywane luki Windows z naszego backendu (CISA KEV).
 * poDacie = data końca wsparcia systemu (YYYY-MM-DD) — tylko nowsze. */
async function pobierzLukiNaZywo(poDacie) {
  try {
    const r = await fetch(API + '/api/skan/luki' + (poDacie ? ('?po=' + encodeURIComponent(poDacie)) : ''),
      { headers: { 'Accept': 'application/json' } });
    if (!r.ok) return [];
    const j = await r.json().catch(() => null);
    return (j && Array.isArray(j.luki)) ? j.luki : [];
  } catch (_) { return []; }
}

window.Skan = { API, DANE, wykryjSystem, wykryjPrzegladarke, wykryjPolaczenie, wykryjSlad, wykryjIP, sprawdzHaslo, maskujHaslo, ocenSile, SAMOAUDYT, policzWynik, ocenZagrozenia, czytajGPU, znaneLuki, pobierzLukiNaZywo };
