/** Lista kancelarii w miejscowości albo najbliżej. Online = terminarz, reszta = zapytanie. */
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { api, linkTelefonu, type Kancelaria } from "../src/api";
import { czcionka, kolory, odstep, promien } from "../src/theme";
import { Ekran, Komunikat, Ladowanie, Odznaka, Przycisk } from "../src/ui";

export default function Kancelarie() {
  const { miasto, lat, lon } = useLocalSearchParams<{ miasto?: string; lat?: string; lon?: string }>();
  const [lista, setLista] = useState<Kancelaria[] | null>(null);
  const [nazwa, setNazwa] = useState("");
  const [blad, setBlad] = useState("");

  const wczytaj = useCallback(() => {
    setBlad("");
    setLista(null);
    const parametry = miasto ? { miasto } : { lat: Number(lat), lon: Number(lon) };
    api
      .kancelarie(parametry)
      .then((odp) => {
        setLista(odp.kancelarie);
        setNazwa(odp.miejscowosc?.nazwa ?? "");
      })
      .catch((e: Error) => {
        setLista([]);
        setBlad(e.message);
      });
  }, [miasto, lat, lon]);

  useEffect(wczytaj, [wczytaj]);

  const otworz = (k: Kancelaria) => {
    if (k.online) {
      router.push(`/kancelaria/${encodeURIComponent(k.id)}`);
    } else {
      const p = new URLSearchParams({
        baza_id: String(k.baza_id ?? ""),
        nazwa: k.nazwa,
        miasto: miasto ?? "",
        miasto_nazwa: nazwa || k.miasto,
      });
      router.push(`/zapytanie?${p.toString()}`);
    }
  };

  return (
    <Ekran>
      <View>
        <Text style={czcionka.tytul}>{nazwa ? `Notariusze: ${nazwa}` : "Kancelarie najbliżej Ciebie"}</Text>
        <Text style={czcionka.pod}>
          {nazwa
            ? "Kancelarie z terminarzem online rezerwujesz od razu. Do pozostałych wysyłasz zapytanie, a kancelaria oddzwania."
            : "Pokazujemy kancelarie, które przyjmują rezerwacje online, od najbliższej."}
        </Text>
      </View>

      {blad ? (
        <>
          <Komunikat rodzaj="blad">{blad}</Komunikat>
          <Przycisk odmiana="drugi" onPress={wczytaj}>Spróbuj ponownie</Przycisk>
        </>
      ) : null}
      {lista === null ? <Ladowanie tekst="Szukam kancelarii..." /> : null}
      {lista && lista.length === 0 && !blad ? (
        <Komunikat>
          {nazwa
            ? "W tej miejscowości nie mamy jeszcze kancelarii. Sprawdź większe miasto w okolicy."
            : "W pobliżu nie ma jeszcze kancelarii z rezerwacją online. Wyszukaj po miejscowości, a wyślemy zapytanie."}
        </Komunikat>
      ) : null}

      {lista?.map((k) => (
        <Pressable
          key={k.id}
          onPress={() => otworz(k)}
          accessibilityRole="button"
          style={({ pressed }) => [styl.karta, k.online && styl.kartaOnline, pressed && { opacity: 0.9 }]}
        >
          <View style={styl.naglowek}>
            <Odznaka kolor={k.online ? kolory.blekit : kolory.tekst2}>{k.online ? "Rezerwacja online" : "Zapytanie o termin"}</Odznaka>
            {k.odleglosc_km != null ? <Text style={czcionka.maly}>{k.odleglosc_km} km</Text> : null}
          </View>
          <Text style={czcionka.naglowek}>{k.nazwa}</Text>
          {k.notariusze && k.notariusze !== k.nazwa ? <Text style={czcionka.pod}>{k.notariusze}</Text> : null}
          {k.adres ? <Text style={czcionka.pod}>{k.adres}</Text> : null}
          <View style={styl.dol}>
            {k.telefony.slice(0, 1).map((t) => (
              <Pressable key={t} onPress={() => Linking.openURL(linkTelefonu(t))} hitSlop={8}>
                <Text style={styl.telefon}>☎ {t}</Text>
              </Pressable>
            ))}
            <Text style={styl.akcja}>{k.online ? "Wybierz godzinę ›" : "Zostaw zapytanie ›"}</Text>
          </View>
        </Pressable>
      ))}
    </Ekran>
  );
}

const styl = StyleSheet.create({
  karta: {
    backgroundColor: kolory.powierzchnia,
    borderRadius: promien.l,
    padding: odstep.l,
    borderWidth: 1,
    borderColor: kolory.linia,
    gap: odstep.xs,
  },
  kartaOnline: { borderColor: kolory.blekit },
  naglowek: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: odstep.xs },
  dol: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: odstep.s },
  telefon: { color: kolory.indygo, fontWeight: "600" },
  akcja: { color: kolory.indygo, fontWeight: "700", marginLeft: "auto" },
});
