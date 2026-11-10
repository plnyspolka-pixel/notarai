/**
 * Moje wizyty: zapisane w telefonie, status odświeżany z serwera (pociągnij w dół
 * albo "Odśwież"), odwołanie i przełożenie. Otwiera się też z linku notarai://wizyty.
 */
import { router, Stack, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Linking, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { api, BladApi, brakPolaczenia, czyMiniona, dataDlugo, linkKalendarza, linkMapy } from "../src/api";
import { usunWizyte, wczytajWizyty, zapiszWizyte, type Wizyta } from "../src/storage";
import { czcionka, kolory, odstep } from "../src/theme";
import { Ekran, Karta, Komunikat, Ladowanie, Odznaka, Przycisk } from "../src/ui";

export default function Wizyty() {
  const [lista, setLista] = useState<Wizyta[] | null>(null);
  const [odwolanie, setOdwolanie] = useState<string>("");   // id wizyty czekającej na drugie kliknięcie
  const [pracuje, setPracuje] = useState<string>("");
  const [blad, setBlad] = useState("");
  const [odswiezam, setOdswiezam] = useState(false);
  const [nieaktualne, setNieaktualne] = useState("");        // statusu nie udało się sprawdzić

  const odswiez = useCallback(async () => {
    const zapisane = await wczytajWizyty();
    setLista(zapisane);
    const doSprawdzenia = zapisane.filter((w) => w.status === "potwierdzona" && w.token && !czyMiniona(w.data, w.koniec || w.godzina));
    if (!doSprawdzenia.length) {
      setNieaktualne("");
      return;
    }
    const swieze = await Promise.allSettled(doSprawdzenia.map((w) => api.rezerwacja(w.id, w.kancelaria.id, w.token)));
    let zmiana = false;
    let bezSieci = 0;
    for (const s of swieze) {
      if (s.status === "fulfilled") {
        await zapiszWizyte(s.value);
        zmiana = true;
      } else if (brakPolaczenia(s.reason) || (s.reason instanceof BladApi && s.reason.status >= 500)) {
        bezSieci += 1;
      }
    }
    setNieaktualne(
      bezSieci
        ? "Nie udało się sprawdzić aktualnego statusu wizyt – brak połączenia. Pokazujemy dane zapisane w telefonie."
        : "",
    );
    if (zmiana) setLista(await wczytajWizyty());
  }, []);

  const odswiezRecznie = useCallback(async () => {
    setOdswiezam(true);
    try {
      await odswiez();
    } finally {
      setOdswiezam(false);
    }
  }, [odswiez]);

  useFocusEffect(
    useCallback(() => {
      odswiez().catch(() => null);
    }, [odswiez]),
  );

  const odwolaj = async (w: Wizyta) => {
    if (odwolanie !== w.id) {
      setOdwolanie(w.id);
      return;
    }
    setPracuje(w.id);
    setBlad("");
    try {
      const r = await api.anuluj(w.id, w.kancelaria.id, w.token);
      await zapiszWizyte(r);
      setLista(await wczytajWizyty());
    } catch (e) {
      setBlad(
        brakPolaczenia(e)
          ? "Nie udało się odwołać wizyty – brak połączenia. Spróbuj ponownie, gdy wróci internet, albo zadzwoń do kancelarii."
          : (e as Error).message,
      );
    } finally {
      setPracuje("");
      setOdwolanie("");
    }
  };

  const usun = async (w: Wizyta) => {
    await usunWizyte(w.id);
    setLista(await wczytajWizyty());
  };

  return (
    <Ekran odswiezanie={{ trwa: odswiezam, onOdswiez: odswiezRecznie }}>
      <Stack.Screen
        options={{
          headerRight: () => (
            <Pressable onPress={odswiezRecznie} hitSlop={10} accessibilityRole="button" accessibilityLabel="Odśwież status wizyt">
              <Text style={styl.odswiez}>{odswiezam ? "..." : "Odśwież"}</Text>
            </Pressable>
          ),
        }}
      />
      {blad ? <Komunikat rodzaj="blad">{blad}</Komunikat> : null}
      {nieaktualne ? <Komunikat>{nieaktualne}</Komunikat> : null}
      {lista === null ? <Ladowanie /> : null}
      {lista && lista.length === 0 ? (
        <>
          <Komunikat>Nie masz jeszcze umówionych wizyt w tym telefonie.</Komunikat>
          <Przycisk onPress={() => router.replace("/")}>Znajdź notariusza</Przycisk>
        </>
      ) : null}
      {lista?.map((w) => {
        const miniona = czyMiniona(w.data, w.koniec || w.godzina);
        const odwolana = w.status === "anulowana";
        const aktywna = !odwolana && !miniona;
        return (
          <Karta key={w.id} style={!aktywna ? { opacity: 0.75 } : undefined}>
            <View style={styl.naglowek}>
              <Odznaka kolor={odwolana ? kolory.alarm : miniona ? kolory.tekst2 : kolory.sukces}>
                {odwolana ? "Odwołana" : miniona ? "Zakończona" : "Potwierdzona"}
              </Odznaka>
              <Text style={czcionka.maly}>{w.godzina}–{w.koniec}</Text>
            </View>
            <Text style={czcionka.naglowek}>{dataDlugo(w.data)}</Text>
            <Text style={czcionka.tekst}>{w.kancelaria.nazwa}</Text>
            <Text style={czcionka.pod}>{w.kancelaria.adres}</Text>
            <Text style={czcionka.maly}>{w.rodzaj_inny || w.rodzaj}</Text>
            {odwolana && w.anulowal === "kancelaria" ? (
              <Text style={[czcionka.pod, { color: kolory.alarm }]}>
                Kancelaria odwołała tę wizytę. Umów nowy termin albo zadzwoń do kancelarii.
              </Text>
            ) : null}
            {aktywna ? (
              <View style={styl.akcje}>
                <Przycisk odmiana="drugi" style={styl.akcja} onPress={() => Linking.openURL(linkMapy(w.kancelaria))}>
                  Nawiguj
                </Przycisk>
                <Przycisk odmiana="drugi" style={styl.akcja} onPress={() => Linking.openURL(linkKalendarza(w))}>
                  Kalendarz
                </Przycisk>
                <Przycisk
                  odmiana="drugi"
                  style={styl.akcja}
                  onPress={() =>
                    // Token zostaje w pamięci telefonu - w adresie (historia przeglądarki) go nie ma.
                    router.push(`/kancelaria/${encodeURIComponent(w.kancelaria.id)}?przeloz=${encodeURIComponent(w.id)}`)
                  }
                >
                  Przełóż
                </Przycisk>
                <Przycisk
                  odmiana={odwolanie === w.id ? "alarm" : "cichy"}
                  style={styl.akcja}
                  ladowanie={pracuje === w.id}
                  onPress={() => odwolaj(w)}
                >
                  {odwolanie === w.id ? "Potwierdź odwołanie" : "Odwołaj"}
                </Przycisk>
              </View>
            ) : (
              <View style={styl.akcje}>
                {odwolana && w.anulowal === "kancelaria" ? (
                  <Przycisk
                    odmiana="drugi"
                    style={styl.akcja}
                    onPress={() => router.push(`/kancelaria/${encodeURIComponent(w.kancelaria.id)}`)}
                  >
                    Umów nowy termin
                  </Przycisk>
                ) : null}
                <Przycisk odmiana="cichy" style={styl.akcja} onPress={() => usun(w)}>
                  Usuń z listy
                </Przycisk>
              </View>
            )}
          </Karta>
        );
      })}
      {lista && lista.length ? (
        <Text style={[czcionka.maly, { textAlign: "center" }]}>
          {Platform.OS === "web"
            ? "Wizyty są zapisane tylko w tej przeglądarce. Po wyczyszczeniu danych strony odwołasz wizytę telefonicznie w kancelarii."
            : "Wizyty są zapisane tylko w tym telefonie. Po usunięciu aplikacji odwołasz wizytę telefonicznie w kancelarii."}
          {Platform.OS === "web" ? "" : " Pociągnij listę w dół, żeby odświeżyć status."}
        </Text>
      ) : null}
    </Ekran>
  );
}

const styl = StyleSheet.create({
  naglowek: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  akcje: { flexDirection: "row", flexWrap: "wrap", gap: odstep.s, marginTop: odstep.s },
  akcja: { minHeight: 40, paddingHorizontal: odstep.m, flexGrow: 1, flexBasis: "45%" },
  odswiez: { color: kolory.zloto, fontWeight: "700", fontSize: 15, paddingHorizontal: odstep.s },
});
