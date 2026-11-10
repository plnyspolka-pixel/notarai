/** Moje wizyty: zapisane w telefonie, status odświeżany z serwera, odwołanie i przełożenie. */
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Linking, StyleSheet, Text, View } from "react-native";
import { api, czyMiniona, dataDlugo, linkKalendarza, linkMapy } from "../src/api";
import { usunWizyte, wczytajWizyty, zapiszWizyte, type Wizyta } from "../src/storage";
import { czcionka, kolory, odstep } from "../src/theme";
import { Ekran, Karta, Komunikat, Ladowanie, Odznaka, Przycisk } from "../src/ui";

export default function Wizyty() {
  const [lista, setLista] = useState<Wizyta[] | null>(null);
  const [odwolanie, setOdwolanie] = useState<string>("");   // id wizyty czekającej na drugie kliknięcie
  const [pracuje, setPracuje] = useState<string>("");
  const [blad, setBlad] = useState("");

  const odswiez = useCallback(async () => {
    const zapisane = await wczytajWizyty();
    setLista(zapisane);
    const swieze = await Promise.allSettled(
      zapisane.filter((w) => w.status === "potwierdzona" && w.token).map((w) => api.rezerwacja(w.id, w.kancelaria.id, w.token)),
    );
    let zmiana = false;
    for (const s of swieze) {
      if (s.status === "fulfilled") {
        await zapiszWizyte(s.value);
        zmiana = true;
      }
    }
    if (zmiana) setLista(await wczytajWizyty());
  }, []);

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
      setBlad((e as Error).message);
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
    <Ekran>
      {blad ? <Komunikat rodzaj="blad">{blad}</Komunikat> : null}
      {lista === null ? <Ladowanie /> : null}
      {lista && lista.length === 0 ? (
        <>
          <Komunikat>Nie masz jeszcze umówionych wizyt w tym telefonie.</Komunikat>
          <Przycisk onPress={() => router.replace("/")}>Znajdź notariusza</Przycisk>
        </>
      ) : null}
      {lista?.map((w) => {
        const miniona = czyMiniona(w.data, w.koniec || w.godzina);
        const aktywna = w.status === "potwierdzona" && !miniona;
        return (
          <Karta key={w.id} style={!aktywna ? { opacity: 0.75 } : undefined}>
            <View style={styl.naglowek}>
              <Odznaka kolor={w.status === "anulowana" ? kolory.alarm : miniona ? kolory.tekst2 : kolory.sukces}>
                {w.status === "anulowana" ? "Odwołana" : miniona ? "Zakończona" : "Potwierdzona"}
              </Odznaka>
              <Text style={czcionka.maly}>{w.godzina}–{w.koniec}</Text>
            </View>
            <Text style={czcionka.naglowek}>{dataDlugo(w.data)}</Text>
            <Text style={czcionka.tekst}>{w.kancelaria.nazwa}</Text>
            <Text style={czcionka.pod}>{w.kancelaria.adres}</Text>
            <Text style={czcionka.maly}>{w.rodzaj_inny || w.rodzaj}</Text>
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
                    router.push(
                      `/kancelaria/${encodeURIComponent(w.kancelaria.id)}?przeloz=${encodeURIComponent(w.id)}&token=${encodeURIComponent(w.token)}`,
                    )
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
              <Przycisk odmiana="cichy" onPress={() => usun(w)}>Usuń z listy</Przycisk>
            )}
          </Karta>
        );
      })}
      {lista && lista.length ? (
        <Text style={[czcionka.maly, { textAlign: "center" }]}>
          Wizyty są zapisane tylko w tym telefonie. Po usunięciu aplikacji odwołasz wizytę telefonicznie w kancelarii.
        </Text>
      ) : null}
    </Ekran>
  );
}

const styl = StyleSheet.create({
  naglowek: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  akcje: { flexDirection: "row", flexWrap: "wrap", gap: odstep.s, marginTop: odstep.s },
  akcja: { minHeight: 40, paddingHorizontal: odstep.m, flexGrow: 1, flexBasis: "45%" },
});
