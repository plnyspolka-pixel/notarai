/** Zapytanie o termin do kancelarii bez terminarza online (istniejący przepływ /api/wizyty). */
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text } from "react-native";
import { api } from "../src/api";
import { czcionka, kolory } from "../src/theme";
import { Ekran, InformacjaPrywatnosc, Karta, Komunikat, Pole, Przycisk, Zaznaczenie } from "../src/ui";

type Parametry = { baza_id?: string; nazwa?: string; miasto?: string; miasto_nazwa?: string };

export default function Zapytanie() {
  const p = useLocalSearchParams<Parametry>();
  const [imie, setImie] = useState("");
  const [telefon, setTelefon] = useState("");
  const [email, setEmail] = useState("");
  const [czynnosc, setCzynnosc] = useState("");
  const [termin, setTermin] = useState("");
  const [wiadomosc, setWiadomosc] = useState("");
  const [zgoda, setZgoda] = useState(false);
  const [bledy, setBledy] = useState<Record<string, string>>({});
  const [pracuje, setPracuje] = useState(false);
  const [blad, setBlad] = useState("");
  const [wynik, setWynik] = useState("");

  const wyslij = async () => {
    const b: Record<string, string> = {};
    if (imie.trim().length < 2) b.imie = "Podaj imię.";
    if (!telefon.trim() && !email.trim()) b.telefon = "Podaj telefon albo e-mail, żeby kancelaria mogła odpowiedzieć.";
    if (czynnosc.trim().length < 2) b.czynnosc = "Napisz, jakiej czynności dotyczy wizyta.";
    if (!zgoda) b.zgoda = "Bez zgody nie przekażemy zapytania.";
    setBledy(b);
    if (Object.keys(b).length) return;
    setBlad("");
    setPracuje(true);
    try {
      const odp = await api.zgloszenie({
        imie: imie.trim(),
        telefon: telefon.trim(),
        email: email.trim(),
        czynnosc: czynnosc.trim(),
        termin: termin.trim(),
        wiadomosc: wiadomosc.trim(),
        zgoda,
        kancelaria: p.baza_id ? Number(p.baza_id) : null,
        miejscowosc: p.miasto ?? "",
      });
      setWynik(odp.komunikat);
    } catch (e) {
      setBlad((e as Error).message);
    } finally {
      setPracuje(false);
    }
  };

  if (wynik) {
    return (
      <Ekran stopka={<Przycisk onPress={() => router.replace("/")}>Na start</Przycisk>}>
        <Komunikat rodzaj="sukces">{wynik}</Komunikat>
        <Text style={czcionka.pod}>
          Ta kancelaria nie prowadzi jeszcze terminarza online w notarai, dlatego termin potwierdzi telefonicznie
          albo e-mailem.
        </Text>
      </Ekran>
    );
  }

  return (
    <Ekran stopka={<Przycisk onPress={wyslij} ladowanie={pracuje}>Wyślij zapytanie</Przycisk>}>
      <Karta style={{ borderColor: kolory.linia2 }}>
        <Text style={czcionka.maly}>KANCELARIA</Text>
        <Text style={czcionka.naglowek}>{p.nazwa || `Notariusz w miejscowości ${p.miasto_nazwa ?? ""}`}</Text>
        <Text style={czcionka.pod}>
          Kancelaria nie udostępnia jeszcze terminarza online. Zostaw kontakt, a skontaktuje się z Tobą, żeby ustalić termin.
        </Text>
      </Karta>
      {blad ? <Komunikat rodzaj="blad">{blad}</Komunikat> : null}
      <Karta>
        <Pole etykieta="Imię i nazwisko" value={imie} onChangeText={setImie} autoCapitalize="words" blad={bledy.imie} />
        <Pole etykieta="Telefon" value={telefon} onChangeText={setTelefon} keyboardType="phone-pad" blad={bledy.telefon} />
        <Pole etykieta="E-mail" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
        <Pole
          etykieta="Czego dotyczy wizyta?"
          value={czynnosc}
          onChangeText={setCzynnosc}
          placeholder="np. umowa sprzedaży mieszkania"
          blad={bledy.czynnosc}
        />
        <Pole etykieta="Preferowany termin" value={termin} onChangeText={setTermin} placeholder="np. przyszły tydzień po 16" />
        <Pole
          etykieta="Wiadomość (opcjonalnie)"
          value={wiadomosc}
          onChangeText={setWiadomosc}
          multiline
          numberOfLines={3}
          style={{ minHeight: 80, textAlignVertical: "top" }}
        />
        <Zaznaczenie zaznaczone={zgoda} onChange={setZgoda}>
          Zgadzam się na przekazanie moich danych kancelarii notarialnej w celu umówienia wizyty.
        </Zaznaczenie>
        {bledy.zgoda ? <Text style={styl.blad}>{bledy.zgoda}</Text> : null}
        <InformacjaPrywatnosc />
      </Karta>
    </Ekran>
  );
}

const styl = StyleSheet.create({
  blad: { ...czcionka.maly, color: kolory.alarm },
});
