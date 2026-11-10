/** Start: szukanie kancelarii po miejscowości albo najbliżej, wejście do "Moje wizyty". */
import * as Location from "expo-location";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { api, type Konfiguracja, type Miejscowosc } from "../src/api";
import { wczytajWizyty } from "../src/storage";
import { czcionka, kolory, odstep, promien } from "../src/theme";
import { Ekran, Karta, Komunikat, Pole, Przycisk } from "../src/ui";

export default function Start() {
  const [konfiguracja, setKonfiguracja] = useState<Konfiguracja | null>(null);
  const [szukane, setSzukane] = useState("");
  const [podpowiedzi, setPodpowiedzi] = useState<Miejscowosc[]>([]);
  const [szukam, setSzukam] = useState(false);
  const [lokalizuje, setLokalizuje] = useState(false);
  const [blad, setBlad] = useState("");
  const [nadchodzace, setNadchodzace] = useState(0);
  const licznik = useRef(0);

  useEffect(() => {
    api.konfiguracja().then(setKonfiguracja).catch(() => setKonfiguracja(null));
  }, []);

  useFocusEffect(
    useCallback(() => {
      wczytajWizyty().then((lista) => setNadchodzace(lista.filter((w) => w.status === "potwierdzona").length));
    }, []),
  );

  useEffect(() => {
    const tekst = szukane.trim();
    if (tekst.length < 2) {
      setPodpowiedzi([]);
      return;
    }
    const numer = ++licznik.current;
    setSzukam(true);
    const t = setTimeout(() => {
      api
        .miejscowosci(tekst)
        .then((odp) => {
          if (numer === licznik.current) setPodpowiedzi(odp.miejscowosci);
        })
        .catch(() => setPodpowiedzi([]))
        .finally(() => numer === licznik.current && setSzukam(false));
    }, 250);
    return () => clearTimeout(t);
  }, [szukane]);

  const najblizej = async () => {
    setBlad("");
    setLokalizuje(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        setBlad("Bez dostępu do lokalizacji wyszukaj kancelarię po miejscowości.");
        return;
      }
      const poz = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      router.push(`/kancelarie?lat=${poz.coords.latitude.toFixed(5)}&lon=${poz.coords.longitude.toFixed(5)}`);
    } catch {
      setBlad("Nie udało się ustalić położenia. Wpisz miejscowość.");
    } finally {
      setLokalizuje(false);
    }
  };

  return (
    <Ekran>
      <View style={styl.hero}>
        <Text style={styl.heroNad}>notarai</Text>
        <Text style={styl.heroTytul}>Umów się do notariusza</Text>
        <Text style={styl.heroPod}>
          Wybierz kancelarię i wolną godzinę. Potwierdzenie przyjdzie SMS-em, a dzień przed wizytą przypomnimy.
        </Text>
      </View>

      {konfiguracja && !konfiguracja.rezerwacje_online ? (
        <Komunikat>
          Rezerwacje online są chwilowo niedostępne. Kancelarie przyjmują zapytania o termin i oddzwaniają.
        </Komunikat>
      ) : null}

      <Karta>
        <Pole
          etykieta="Miejscowość"
          placeholder="np. Lublin"
          value={szukane}
          onChangeText={setSzukane}
          autoCorrect={false}
          autoCapitalize="words"
          returnKeyType="search"
          accessibilityLabel="Miejscowość"
        />
        {podpowiedzi.length ? (
          <View style={styl.lista}>
            {podpowiedzi.map((m) => (
              <Pressable
                key={m.slug}
                onPress={() => {
                  setSzukane(m.nazwa);
                  setPodpowiedzi([]);
                  router.push(`/kancelarie?miasto=${encodeURIComponent(m.slug)}`);
                }}
                style={({ pressed }) => [styl.pozycja, pressed && { backgroundColor: kolory.tlo }]}
              >
                <Text style={czcionka.tekst}>{m.nazwa}</Text>
                <Text style={czcionka.maly}>
                  {m.liczba} {m.liczba === 1 ? "kancelaria" : m.liczba < 5 ? "kancelarie" : "kancelarii"}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : szukane.trim().length >= 2 && !szukam ? (
          <Text style={czcionka.pod}>Nie znamy takiej miejscowości. Spróbuj większego miasta w okolicy.</Text>
        ) : null}
        <Przycisk onPress={najblizej} odmiana="drugi" ladowanie={lokalizuje}>
          Najbliżej mnie
        </Przycisk>
        {blad ? <Text style={[czcionka.maly, { color: kolory.alarm }]}>{blad}</Text> : null}
      </Karta>

      <Pressable onPress={() => router.push("/wizyty")} style={({ pressed }) => [styl.kafel, pressed && { opacity: 0.9 }]}>
        <View style={{ flex: 1 }}>
          <Text style={[czcionka.naglowek, { color: "#fff" }]}>Moje wizyty</Text>
          <Text style={[czcionka.pod, { color: "#d6ddf2" }]}>
            {nadchodzace ? `${nadchodzace} ${nadchodzace === 1 ? "umówiona wizyta" : "umówione wizyty"}` : "Tu zobaczysz umówione terminy"}
          </Text>
        </View>
        <Text style={{ color: kolory.zloto, fontSize: 28 }}>›</Text>
      </Pressable>

      <Karta>
        <Text style={czcionka.naglowek}>Ile zapłacę u notariusza?</Text>
        <Text style={czcionka.pod}>Kalkulator taksy notarialnej policzy orientacyjny koszt czynności przed wizytą.</Text>
        <Przycisk odmiana="cichy" onPress={() => Linking.openURL(`${konfiguracja?.strona ?? "https://notarai.pl"}/kalkulator/`)}>
          Otwórz kalkulator
        </Przycisk>
      </Karta>

      <Text style={[czcionka.maly, { textAlign: "center" }]}>
        Aplikacja przekazuje Twoje dane wyłącznie wybranej kancelarii. Nie zakładasz konta.
      </Text>
      <Pressable onPress={() => router.push("/o-aplikacji")} accessibilityRole="link" hitSlop={8}>
        <Text style={[czcionka.maly, styl.oAplikacji]}>O aplikacji · kontakt · prywatność</Text>
      </Pressable>
    </Ekran>
  );
}

const styl = StyleSheet.create({
  hero: {
    backgroundColor: kolory.granat,
    borderRadius: promien.l,
    padding: odstep.xl,
    gap: odstep.s,
  },
  heroNad: { color: kolory.zloto, fontWeight: "700", letterSpacing: 2, textTransform: "uppercase", fontSize: 12 },
  heroTytul: { color: "#fff", fontSize: 28, fontWeight: "800", lineHeight: 34 },
  heroPod: { color: "#d6ddf2", fontSize: 15, lineHeight: 21 },
  lista: { borderWidth: 1, borderColor: kolory.linia, borderRadius: promien.m, overflow: "hidden", marginTop: -odstep.s },
  pozycja: {
    paddingHorizontal: odstep.m,
    paddingVertical: odstep.m,
    borderBottomWidth: 1,
    borderBottomColor: kolory.linia,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  oAplikacji: { textAlign: "center", color: kolory.indygo, fontWeight: "600" },
  kafel: {
    backgroundColor: kolory.indygo,
    borderRadius: promien.l,
    padding: odstep.l,
    flexDirection: "row",
    alignItems: "center",
    gap: odstep.m,
  },
});
