/* Silnik "Klikamy" w rozszerzeniu: model prowadzi strone, notariusz patrzy.

   To ta sama petla co pomocnik/klikamy.py, tylko w przegladarce notariusza.
   Zabezpieczenia siedza tutaj, w mechanizmie, a nie w poleceniu dla modelu -
   prompt mozna przegadac, zwlaszcza trescia strony, ktora model czyta:

     - model wybiera element z ponumerowanej listy, nie wspolrzedne,
     - elementu, ktory wysyla, sklada, podpisuje albo placi, nie da sie
       kliknac - stery wracaja do czlowieka. Dzieki temu podpis elektroniczny
       zostaje tam, gdzie byl: notariusz klika "Podpisz" sam, a wtyczka podpisu
       i okno PIN-u dzialaja w jego przegladarce jak zawsze,
     - do pola hasla i PIN-u nie wpisujemy nic, nigdy,
     - agent nie wychodzi poza strone, na ktorej notariusz go uruchomil,
     - strony logowania nie czytamy i nie wysylamy do modelu: gdy sesja wygasla
       albo serwis prosi o logowanie, czekamy, az notariusz zaloguje sie sam
       (haslo, profil zaufany, podpis, PIN), i wznawiamy od miejsca przerwania,
     - liczba krokow jest ograniczona.

   Plik nie dotyka chrome.* ani DOM - strone i model dostaje z zewnatrz, wiec
   da sie go sprawdzic w samym Node (testy/silnik.test.mjs). */

export const MAKS_KROKOW = 20;

/* Czynnosci o skutku zewnetrznym, rozpoznawane po opisie elementu. Lepiej
   zatrzymac sie raz za duzo niz raz za malo: zatrzymanie kosztuje klikniecie
   notariusza, a wyslanie wniosku kosztuje postepowanie. */
export const WYSYLKA_ZRODLO =
  "wy[sś]l|wy[sś]lij|z[łl][oó][żz]|podpis|zatwierd[zź]|zap[łl]a|p[łl]atno|" +
  "op[łl]a[ćc]|umie[śs][ćc]|usu[ńn]|skasuj|potwierd[zź]|zam[óo]w|kup|" +
  "akceptuj[eę]|submit|send|sign(?!\\s*(in|up))|pay|delete|confirm";
export const WYSYLKA = new RegExp(WYSYLKA_ZRODLO, "i");

export const AKCJE = ["kliknij", "wpisz", "wybierz", "otworz", "czytaj", "pytam", "koniec"];

/* czeka: na co czekamy od czlowieka, zeby dalo sie wznowic prace:
   "logowanie" - ma sie zalogowac, "czynnosc" - ma sam wyslac/podpisac/zaplacic. */
export class Odmowa extends Error {
  constructor(tresc, czeka = "") { super(tresc); this.czeka = czeka; }
}

/* Serwisy logowania, do ktorych portale urzedowe odsylaja. Tam nie pracujemy. */
const LOGOWANIE_HOSTY = ["login.gov.pl", "pz.gov.pl"];
const LOGOWANIE_SCIEZKA = /\/(login|logowanie|zaloguj|signin|sign-in|auth|oauth2?|sso|saml)(\/|\?|$)/i;
const LOGOWANIE_TEKST = /zaloguj|logowani|log in|sign in/i;
const SESJA_WYGASLA = new RegExp(
  "sesja (wygas[łl]a|zosta[łl]a zako[ńn]czona|utraci[łl]a wa[żz]no[śs][ćc])|" +
  "zosta[łl]e[śs] wylogowan|zaloguj si[ęe] ponownie|session (has )?expired", "i");

/* Czy to strona logowania albo komunikat o wygaslej sesji. Rozpoznajemy po
   polu hasla, po znanym serwisie logowania, po adresie razem z trescia albo po
   komunikacie. Lepiej zatrzymac sie raz za duzo: kosztuje to jedno klikniecie. */
export function jestLogowanie(stan) {
  if (!stan) return false;
  if ((stan.elementy || []).some(e => e.typ === "password")) return true;
  if (wolnoWejsc(stan.adres, LOGOWANIE_HOSTY)) return true;
  const tekst = String(stan.tekst || "");
  if (SESJA_WYGASLA.test(tekst)) return true;
  let sciezka = "";
  try { sciezka = new URL(stan.adres).pathname; } catch { return false; }
  return LOGOWANIE_SCIEZKA.test(sciezka) && LOGOWANIE_TEKST.test(tekst);
}

export function host(adres) {
  try { return new URL(adres).hostname.toLowerCase(); } catch { return ""; }
}

export function wolnoWejsc(adres, dozwolone) {
  let cel;
  try { cel = new URL(adres); } catch { return false; }
  if (cel.protocol !== "https:" && cel.protocol !== "http:") return false;
  const nazwa = cel.hostname.toLowerCase();
  return dozwolone.some(h => h && (nazwa === h || nazwa.endsWith("." + h)));
}

/* Serwer i model dostaja opis strony bez selektorow: te zostaja tutaj. */
export function stanDlaModelu(stan) {
  return {
    adres: stan.adres,
    tekst: stan.tekst,
    elementy: stan.elementy.map(e => ({ nr: e.nr, rola: e.rola, opis: e.opis })),
  };
}

/* W historii dla modelu nie ma wpisywanych wartosci - tylko czynnosc i cel. */
export function krokDlaModelu(krok) {
  return { nr: krok.nr, akcja: krok.akcja, cel: krok.cel, uwaga: krok.uwaga };
}

function element(stan, nr) {
  const znaleziony = stan.elementy.find(e => e.nr === Number(nr));
  if (!znaleziony) throw new Odmowa(`Na stronie nie ma elementu o numerze ${nr}.`);
  return znaleziony;
}

/* strona:  { stan(), kliknij(el), wpisz(el, tekst), wybierz(el, tekst), otworz(adres) }
   model:   async (cel, stanDlaModelu, kroki) => { akcja, nr, tekst, adres, ... }
   opcje:   { maksKrokow, przerwij: () => bool, naKrok: (krok) => void,
              wznow: { kroki, dozwolone } - poprzedni przebieg, gdy czlowiek
              zrobil swoje (zalogowal sie, podpisal) i prosi o ciag dalszy }
   wynik:   przebieg.czeka mowi, czy i na co czekamy; przebieg.dozwolone trzeba
            oddac we wznow, zeby po logowaniu wrocic na ten sam serwis. */
export async function prowadz(cel, strona, model, opcje = {}) {
  const maks = opcje.maksKrokow || MAKS_KROKOW;
  const wznow = opcje.wznow || {};
  const przebieg = { kroki: (wznow.kroki || []).slice(), podsumowanie: "", pytanie: "",
                     zatrzymano: "", czeka: "", dozwolone: null };
  let dozwolone = Array.isArray(wznow.dozwolone) && wznow.dozwolone.length
    ? wznow.dozwolone.slice() : null;
  przebieg.dozwolone = dozwolone;
  const poprzednie = przebieg.kroki.length;

  for (let numer = poprzednie + 1; numer <= poprzednie + maks; numer++) {
    if (opcje.przerwij && opcje.przerwij()) {
      przebieg.zatrzymano = "Zatrzymane na Twoje polecenie.";
      return przebieg;
    }
    const krok = { nr: numer, akcja: "", cel: "", mysl: "", uwaga: "", wykonano: false };
    try {
      const stan = await strona.stan();
      // Strony logowania nie pokazujemy modelowi i nie zapamietujemy jej adresu
      // jako miejsca pracy: logowanie nalezy do czlowieka.
      if (jestLogowanie(stan)) {
        krok.akcja = "czekam";
        krok.cel = "logowanie";
        throw new Odmowa("Ten serwis prosi o logowanie albo sesja wygasła. Zaloguj się " +
                         "samodzielnie - hasło, podpis i PIN należą do Ciebie - " +
                         "a potem kliknij „Wznów”.", "logowanie");
      }
      if (dozwolone === null) { dozwolone = [host(stan.adres)]; przebieg.dozwolone = dozwolone; }
      // Strona sama przeszla gdzie indziej.
      if (!wolnoWejsc(stan.adres, dozwolone)) {
        throw new Odmowa(`Strona przeszła na ${host(stan.adres) || "inny adres"}. ` +
                         "Tam nie pracuję - przejmij stery i uruchom mnie ponownie.");
      }
      const wybor = (await model(cel, stanDlaModelu(stan),
                                 przebieg.kroki.map(krokDlaModelu))) || {};
      krok.akcja = String(wybor.akcja || "").trim();
      krok.mysl = String(wybor.mysl || "").slice(0, 300);
      przebieg.kroki.push(krok);

      if (!AKCJE.includes(krok.akcja)) {
        krok.uwaga = `Nieznana czynność: ${krok.akcja || "brak"}`;
        przebieg.zatrzymano = krok.uwaga;
      } else if (krok.akcja === "koniec") {
        przebieg.podsumowanie = String(wybor.podsumowanie || "").slice(0, 600);
        krok.wykonano = true;
      } else if (krok.akcja === "pytam") {
        przebieg.pytanie = String(wybor.pytanie || "").slice(0, 400) ||
                           "Nie wiem, co zrobić dalej. Przejmij stery.";
        krok.wykonano = true;
      } else {
        await wykonaj(krok, wybor, stan, strona, dozwolone);
      }
    } catch (blad) {
      if (!przebieg.kroki.includes(krok)) przebieg.kroki.push(krok);
      krok.uwaga = String(blad && blad.message || blad);
      if (blad instanceof Odmowa) { przebieg.pytanie = krok.uwaga; przebieg.czeka = blad.czeka; }
      else przebieg.zatrzymano = krok.uwaga;
    }
    if (opcje.naKrok) opcje.naKrok(krok);
    if (przebieg.podsumowanie || przebieg.pytanie || przebieg.zatrzymano ||
        krok.akcja === "koniec") return przebieg;
  }
  przebieg.zatrzymano = `Zatrzymałem się po ${maks} krokach. Napisz, co zrobić dalej.`;
  return przebieg;
}

async function wykonaj(krok, wybor, stan, strona, dozwolone) {
  if (krok.akcja === "czytaj") {
    krok.cel = "odczyt strony";
    krok.wykonano = true;
    return;
  }
  if (krok.akcja === "otworz") {
    const adres = String(wybor.adres || "");
    if (!wolnoWejsc(adres, dozwolone)) {
      throw new Odmowa(`Nie wejdę na ${host(adres) || "ten adres"} - ` +
                       "pracuję tylko na stronie, na której mnie uruchomiono.");
    }
    krok.cel = host(adres);
    await strona.otworz(adres);
    krok.wykonano = true;
    return;
  }

  const el = element(stan, wybor.nr);
  krok.cel = String(el.opis || "").slice(0, 100);

  if (krok.akcja === "kliknij") {
    if (WYSYLKA.test(el.opis || "")) {
      throw new Odmowa(`Nie kliknę „${krok.cel}”. To czynność o skutku zewnętrznym - ` +
                       "wysyła, składa albo podpisuje. Zrób to samodzielnie, " +
                       "gdy sprawdzisz treść. Jeśli mam potem pracować dalej, " +
                       "kliknij „Wznów”.", "czynnosc");
    }
    await strona.kliknij(el);
  } else if (krok.akcja === "wpisz") {
    if (el.typ === "password") {
      throw new Odmowa("To pole hasła. Hasło i PIN wpisujesz wyłącznie Ty.");
    }
    await strona.wpisz(el, String(wybor.tekst || ""));
  } else {
    await strona.wybierz(el, String(wybor.tekst || ""));
  }
  krok.wykonano = true;
}
