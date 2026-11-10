/** Formularz rezerwacji: dane klienta, zgoda, kod SMS, zapis wizyty w telefonie. */
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { api, dataDlugo, type Konfiguracja } from "../src/api";
import { zapiszWizyte } from "../src/storage";
import { czcionka, kolory, odstep } from "../src/theme";
import { Ekran, InformacjaPrywatnosc, Karta, Komunikat, Pole, Przycisk, Wybor, Zaznaczenie } from "../src/ui";

type Parametry = { kancelaria: string; nazwa: string; adres: string; data: string; godzina: string; koniec: string };

export default function Rezerwacja() {
  const p = useLocalSearchParams<Parametry>();
  const [konfiguracja, setKonfiguracja] = useState<Konfiguracja | null>(null);
  const [imie, setImie] = useState("");
  const [telefon, setTelefon] = useState("");
  const [email, setEmail] = useState("");
  const [rodzaj, setRodzaj] = useState<string>("");
  const [rodzajInny, setRodzajInny] = useState("");
  const [uwagi, setUwagi] = useState("");
  const [zgoda, setZgoda] = useState(false);
  const [bledy, setBledy] = useState<Record<string, string>>({});
  const [krok, setKrok] = useState<"dane" | "kod">("dane");
  const [weryfikacja, setWeryfikacja] = useState<{ id: string; koncowka: string; testowy: boolean } | null>(null);
  const [kod, setKod] = useState("");
  const [pracuje, setPracuje] = useState(false);
  const [blad, setBlad] = useState("");
  const [zajety, setZajety] = useState(false);

  useEffect(() => {
    api.konfiguracja().then(setKonfiguracja).catch(() => null);
  }, []);

  const sprawdz = () => {
    const b: Record<string, string> = {};
    if (imie.trim().length < 2) b.imie = "Podaj imię i nazwisko.";
    if (telefon.replace(/\D/g, "").length < 9) b.telefon = "Podaj numer telefonu komórkowego (9 cyfr).";
    if (email && !/^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$/.test(email.trim())) b.email = "To nie wygląda na adres e-mail.";
    if (!rodzaj) b.rodzaj = "Wybierz rodzaj czynności.";
    if (rodzaj === "inne" && rodzajInny.trim().length < 2) b.rodzajInny = "Napisz, jakiej czynności dotyczy wizyta.";
    if (!zgoda) b.zgoda = "Bez zgody kancelaria nie może przyjąć rezerwacji.";
    setBledy(b);
    return Object.keys(b).length === 0;
  };

  const wyslijKod = async () => {
    setBlad("");
    if (!sprawdz()) return;
    setPracuje(true);
    try {
      const w = await api.weryfikacja(telefon.trim());
      setWeryfikacja({ id: w.id, koncowka: w.koncowka, testowy: !!w.kod_testowy });
      setKod(w.kod_testowy ?? "");
      setKrok("kod");
    } catch (e) {
      setBlad((e as Error).message);
    } finally {
      setPracuje(false);
    }
  };

  const potwierdz = async () => {
    if (!weryfikacja) return;
    if (kod.trim().length !== 6) {
      setBlad("Wpisz sześciocyfrowy kod z SMS-a.");
      return;
    }
    setBlad("");
    setPracuje(true);
    try {
      const r = await api.rezerwuj({
        kancelaria: p.kancelaria,
        data: p.data,
        godzina: p.godzina,
        rodzaj,
        rodzaj_inny: rodzaj === "inne" ? rodzajInny.trim() : "",
        imie: imie.trim(),
        telefon: telefon.trim(),
        email: email.trim(),
        uwagi: uwagi.trim(),
        zgoda,
        weryfikacja: weryfikacja.id,
        kod: kod.trim(),
      });
      await zapiszWizyte(r, r.token);
      router.replace(`/potwierdzenie?id=${encodeURIComponent(r.id)}`);
    } catch (e) {
      const status = (e as { status?: number }).status;
      setBlad((e as Error).message);
      if (status === 409) setZajety(true);
      if (status === 400 && /nowy/i.test((e as Error).message)) {
        setKrok("dane");
        setWeryfikacja(null);
      }
    } finally {
      setPracuje(false);
    }
  };

  return (
    <Ekran
      stopka={
        krok === "dane" ? (
          <Przycisk onPress={wyslijKod} ladowanie={pracuje}>Wyślij kod SMS</Przycisk>
        ) : (
          <Przycisk onPress={potwierdz} ladowanie={pracuje} wylaczony={zajety}>Potwierdź rezerwację</Przycisk>
        )
      }
    >
      <Karta style={{ borderColor: kolory.blekit }}>
        <Text style={czcionka.maly}>WYBRANY TERMIN</Text>
        <Text style={czcionka.naglowek}>
          {dataDlugo(p.data)}, {p.godzina}–{p.koniec}
        </Text>
        <Text style={czcionka.tekst}>{p.nazwa}</Text>
        <Text style={czcionka.pod}>{p.adres}</Text>
      </Karta>

      {blad ? <Komunikat rodzaj="blad">{blad}</Komunikat> : null}
      {zajety ? (
        <Przycisk odmiana="drugi" onPress={() => router.back()}>Wybierz inną godzinę</Przycisk>
      ) : null}

      {krok === "dane" ? (
        <Karta>
          <Pole
            etykieta="Imię i nazwisko"
            value={imie}
            onChangeText={setImie}
            autoCapitalize="words"
            autoComplete="name"
            textContentType="name"
            blad={bledy.imie}
          />
          <Pole
            etykieta="Telefon komórkowy"
            value={telefon}
            onChangeText={setTelefon}
            keyboardType="phone-pad"
            autoComplete="tel"
            textContentType="telephoneNumber"
            placeholder="600 000 000"
            blad={bledy.telefon}
            pomoc="Na ten numer wyślemy kod i potwierdzenie wizyty."
          />
          <Pole
            etykieta="E-mail (opcjonalnie)"
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            textContentType="emailAddress"
            blad={bledy.email}
          />
          <View style={{ marginBottom: odstep.l, gap: odstep.s }}>
            <Text style={styl.etykieta}>Rodzaj czynności</Text>
            <Wybor opcje={konfiguracja?.rodzaje ?? []} wartosc={rodzaj} onChange={setRodzaj} />
            {bledy.rodzaj ? <Text style={styl.blad}>{bledy.rodzaj}</Text> : null}
          </View>
          {rodzaj === "inne" ? (
            <Pole etykieta="Jaka to czynność?" value={rodzajInny} onChangeText={setRodzajInny} blad={bledy.rodzajInny} />
          ) : null}
          <Pole
            etykieta="Uwagi dla kancelarii (opcjonalnie)"
            value={uwagi}
            onChangeText={setUwagi}
            multiline
            numberOfLines={3}
            style={{ minHeight: 80, textAlignVertical: "top" }}
            placeholder="np. sprzedaż mieszkania, kupujący bierze kredyt"
          />
          <Zaznaczenie zaznaczone={zgoda} onChange={setZgoda}>
            Zgadzam się na przekazanie moich danych wybranej kancelarii notarialnej w celu umówienia i obsługi wizyty.
            Kancelaria jest administratorem tych danych; notarai nie wykorzystuje ich do innych celów.
          </Zaznaczenie>
          {bledy.zgoda ? <Text style={styl.blad}>{bledy.zgoda}</Text> : null}
          <InformacjaPrywatnosc />
        </Karta>
      ) : (
        <Karta>
          <Text style={czcionka.naglowek}>Kod z SMS-a</Text>
          <Text style={czcionka.pod}>
            Wysłaliśmy kod na numer kończący się na {weryfikacja?.koncowka}. Wpisz go, żeby potwierdzić rezerwację.
          </Text>
          {weryfikacja?.testowy ? <Komunikat>Tryb testowy serwera: kod wpisał się sam, SMS nie wyszedł.</Komunikat> : null}
          <Pole
            etykieta="Kod (6 cyfr)"
            value={kod}
            onChangeText={(t) => setKod(t.replace(/\D/g, "").slice(0, 6))}
            keyboardType="number-pad"
            autoComplete="one-time-code"
            textContentType="oneTimeCode"
            maxLength={6}
            style={{ fontSize: 24, letterSpacing: 6, textAlign: "center" }}
          />
          <Przycisk
            odmiana="cichy"
            onPress={() => {
              setKrok("dane");
              setWeryfikacja(null);
              setKod("");
              setBlad("");
            }}
          >
            Zmień numer albo wyślij kod ponownie
          </Przycisk>
        </Karta>
      )}
    </Ekran>
  );
}

const styl = StyleSheet.create({
  etykieta: { ...czcionka.pod, color: kolory.tekst },
  blad: { ...czcionka.maly, color: kolory.alarm },
});
