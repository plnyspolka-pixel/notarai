/** Ekran po udanej rezerwacji: szczegóły, kalendarz, nawigacja. */
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Linking, StyleSheet, Text, View } from "react-native";
import { dataDlugo, linkKalendarza, linkMapy } from "../src/api";
import { znajdzWizyte, type Wizyta } from "../src/storage";
import { czcionka, kolory, odstep } from "../src/theme";
import { Ekran, Karta, Ladowanie, Przycisk } from "../src/ui";

export default function Potwierdzenie() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [w, setW] = useState<Wizyta | null | undefined>(undefined);

  useEffect(() => {
    znajdzWizyte(id).then((x) => setW(x ?? null));
  }, [id]);

  if (w === undefined) return <Ekran><Ladowanie /></Ekran>;
  if (!w) {
    return (
      <Ekran>
        <Text style={czcionka.tekst}>Nie znaleźliśmy tej wizyty w telefonie.</Text>
        <Przycisk onPress={() => router.replace("/")}>Na start</Przycisk>
      </Ekran>
    );
  }

  return (
    <Ekran
      stopka={
        <View style={{ gap: odstep.s }}>
          <Przycisk onPress={() => router.replace("/wizyty")}>Moje wizyty</Przycisk>
          <Przycisk odmiana="cichy" onPress={() => router.replace("/")}>Na start</Przycisk>
        </View>
      }
    >
      <View style={styl.ikona}>
        <Text style={styl.ikonaTekst}>✓</Text>
      </View>
      <Text style={[czcionka.tytul, { textAlign: "center" }]}>Wizyta umówiona</Text>
      <Text style={[czcionka.pod, { textAlign: "center" }]}>
        Potwierdzenie wysłaliśmy SMS-em. Dzień przed wizytą przypomnimy.
      </Text>

      <Karta>
        <Text style={czcionka.maly}>TERMIN</Text>
        <Text style={czcionka.naglowek}>
          {dataDlugo(w.data)}, {w.godzina}–{w.koniec}
        </Text>
        <Text style={czcionka.maly}>KANCELARIA</Text>
        <Text style={czcionka.tekst}>{w.kancelaria.nazwa}</Text>
        <Text style={czcionka.pod}>{w.kancelaria.adres}</Text>
        <Text style={czcionka.maly}>CZYNNOŚĆ</Text>
        <Text style={czcionka.tekst}>{w.rodzaj_inny || w.rodzaj}</Text>
      </Karta>

      <Karta>
        <Text style={czcionka.naglowek}>Co wziąć na wizytę</Text>
        <Text style={czcionka.pod}>
          Dowód osobisty każdej osoby stawającej do czynności. Resztę dokumentów (np. numer księgi wieczystej, akt
          własności) kancelaria wskaże, jeśli będzie potrzebna, dlatego warto podać e-mail albo odebrać telefon.
        </Text>
      </Karta>

      <View style={{ gap: odstep.s }}>
        <Przycisk odmiana="drugi" onPress={() => Linking.openURL(linkKalendarza(w))}>Dodaj do kalendarza</Przycisk>
        <Przycisk odmiana="drugi" onPress={() => Linking.openURL(linkMapy(w.kancelaria))}>Nawiguj do kancelarii</Przycisk>
      </View>
    </Ekran>
  );
}

const styl = StyleSheet.create({
  ikona: {
    alignSelf: "center",
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: kolory.sukcesTlo,
    alignItems: "center",
    justifyContent: "center",
    marginTop: odstep.l,
  },
  ikonaTekst: { color: kolory.sukces, fontSize: 36, fontWeight: "800" },
});
