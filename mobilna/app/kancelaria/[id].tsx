/**
 * Kancelaria online: dane, pasek dni i wolne godziny. Wybór godziny prowadzi
 * do formularza rezerwacji albo (z parametrem `przeloz`) przekłada istniejącą wizytę.
 */
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import {
  api,
  dataDlugo,
  dataKrotko,
  dataZIso,
  isoZDaty,
  linkMapy,
  linkTelefonu,
  type Terminy,
} from "../../src/api";
import { zapiszWizyte } from "../../src/storage";
import { czcionka, kolory, odstep, promien } from "../../src/theme";
import { Ekran, Karta, Komunikat, Ladowanie, Przycisk } from "../../src/ui";

const DNI_NARAZ = 14;

export default function Kancelaria() {
  const { id, przeloz, token } = useLocalSearchParams<{ id: string; przeloz?: string; token?: string }>();
  const [od, setOd] = useState<string | undefined>(undefined);
  const [terminy, setTerminy] = useState<Terminy | null>(null);
  const [blad, setBlad] = useState("");
  const [dzien, setDzien] = useState("");
  const [godzina, setGodzina] = useState("");
  const [zapisuje, setZapisuje] = useState(false);

  const wczytaj = useCallback(() => {
    setBlad("");
    setTerminy(null);
    api
      .terminy(id, od, DNI_NARAZ)
      .then((t) => {
        setTerminy(t);
        const pierwszy = t.dni.find((d) => d.terminy.length);
        setDzien(pierwszy?.data ?? t.dni[0]?.data ?? "");
        setGodzina("");
      })
      .catch((e: Error) => setBlad(e.message));
  }, [id, od]);

  useEffect(wczytaj, [wczytaj]);

  const wybrany = useMemo(() => terminy?.dni.find((d) => d.data === dzien), [terminy, dzien]);
  const koniec = wybrany?.terminy.find((t) => t.godzina === godzina)?.koniec ?? "";
  const horyzont = terminy ? dataZIso(terminy.od) : null;
  const dalejMozliwe =
    !!terminy && !!horyzont && (horyzont.getTime() - Date.now()) / 86400000 + DNI_NARAZ < terminy.max_dni;

  const nastepne = (kierunek: 1 | -1) => {
    if (!terminy) return;
    const d = dataZIso(terminy.od);
    d.setDate(d.getDate() + kierunek * DNI_NARAZ);
    setOd(d < new Date() ? undefined : isoZDaty(d));
  };

  const dalej = async () => {
    if (!terminy || !dzien || !godzina) return;
    const k = terminy.kancelaria;
    if (przeloz && token) {
      setZapisuje(true);
      setBlad("");
      try {
        const r = await api.przeloz(przeloz, k.id, token, dzien, godzina);
        await zapiszWizyte(r, token);
        router.replace("/wizyty");
      } catch (e) {
        setBlad((e as Error).message);
        if ((e as { status?: number }).status === 409) wczytaj();
      } finally {
        setZapisuje(false);
      }
      return;
    }
    const p = new URLSearchParams({ kancelaria: k.id, nazwa: k.nazwa, adres: k.adres, data: dzien, godzina, koniec });
    router.push(`/rezerwacja?${p.toString()}`);
  };

  const k = terminy?.kancelaria;

  return (
    <Ekran
      stopka={
        <View style={{ gap: odstep.s }}>
          <Text style={czcionka.pod}>
            {dzien && godzina ? `${dataDlugo(dzien)}, ${godzina}–${koniec}` : "Wybierz dzień i godzinę"}
          </Text>
          <Przycisk onPress={dalej} wylaczony={!dzien || !godzina} ladowanie={zapisuje}>
            {przeloz ? "Przełóż na ten termin" : "Dalej"}
          </Przycisk>
        </View>
      }
    >
      {przeloz ? <Komunikat>Wybierz nowy termin wizyty. Poprzedni zostanie zwolniony.</Komunikat> : null}
      {blad ? (
        <>
          <Komunikat rodzaj="blad">{blad}</Komunikat>
          <Przycisk odmiana="drugi" onPress={wczytaj}>Spróbuj ponownie</Przycisk>
        </>
      ) : null}
      {!terminy && !blad ? <Ladowanie tekst="Sprawdzam wolne terminy..." /> : null}

      {k ? (
        <Karta>
          <Text style={czcionka.naglowek}>{k.nazwa}</Text>
          {k.notariusze ? <Text style={czcionka.pod}>{k.notariusze}</Text> : null}
          <Text style={czcionka.pod}>{k.adres}</Text>
          <Text style={czcionka.maly}>Wizyta trwa {terminy?.czas_minut} minut. Weź dowód osobisty.</Text>
          <View style={styl.linki}>
            <Pressable onPress={() => Linking.openURL(linkMapy(k))} hitSlop={8}>
              <Text style={styl.link}>Nawiguj</Text>
            </Pressable>
            {k.telefony[0] ? (
              <Pressable onPress={() => Linking.openURL(linkTelefonu(k.telefony[0]))} hitSlop={8}>
                <Text style={styl.link}>Zadzwoń {k.telefony[0]}</Text>
              </Pressable>
            ) : null}
          </View>
        </Karta>
      ) : null}

      {terminy ? (
        <View style={{ gap: odstep.m }}>
          <View style={styl.pasekNaglowek}>
            <Pressable onPress={() => nastepne(-1)} disabled={!od} hitSlop={8}>
              <Text style={[styl.link, !od && { opacity: 0.3 }]}>‹ wcześniej</Text>
            </Pressable>
            <Text style={czcionka.pod}>{dataKrotko(terminy.od).miesiac.toUpperCase()}</Text>
            <Pressable onPress={() => nastepne(1)} disabled={!dalejMozliwe} hitSlop={8}>
              <Text style={[styl.link, !dalejMozliwe && { opacity: 0.3 }]}>później ›</Text>
            </Pressable>
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: odstep.s }}>
            {terminy.dni.map((d) => {
              const brak = d.nieczynne || d.terminy.length === 0;
              const aktywny = d.data === dzien;
              const { dzien: nazwa, numer } = dataKrotko(d.data);
              return (
                <Pressable
                  key={d.data}
                  onPress={() => {
                    setDzien(d.data);
                    setGodzina("");
                  }}
                  disabled={brak}
                  accessibilityRole="button"
                  accessibilityLabel={`${dataDlugo(d.data)}${brak ? ", brak terminów" : ""}`}
                  style={[styl.dzien, aktywny && styl.dzienAktywny, brak && styl.dzienBrak]}
                >
                  <Text style={[czcionka.maly, aktywny && { color: "#d6ddf2" }]}>{nazwa}</Text>
                  <Text style={[styl.dzienNumer, aktywny && { color: "#fff" }]}>{numer}</Text>
                  <Text style={[czcionka.maly, aktywny && { color: "#d6ddf2" }]}>
                    {d.nieczynne ? "zamkn." : d.terminy.length ? `${d.terminy.length} wol.` : "brak"}
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>

          {wybrany ? (
            <Karta>
              <Text style={czcionka.naglowek}>{dataDlugo(wybrany.data)}</Text>
              {wybrany.terminy.length === 0 ? (
                <Text style={czcionka.pod}>
                  {wybrany.nieczynne ? "Kancelaria jest tego dnia nieczynna." : "Brak wolnych godzin. Sprawdź inny dzień."}
                </Text>
              ) : (
                <View style={styl.siatka}>
                  {wybrany.terminy.map((t) => {
                    const aktywna = t.godzina === godzina;
                    return (
                      <Pressable
                        key={t.godzina}
                        onPress={() => setGodzina(t.godzina)}
                        accessibilityRole="button"
                        accessibilityState={{ selected: aktywna }}
                        style={[styl.slot, aktywna && styl.slotAktywny]}
                      >
                        <Text style={[styl.slotTekst, aktywna && { color: "#fff" }]}>{t.godzina}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              )}
            </Karta>
          ) : null}
        </View>
      ) : null}
    </Ekran>
  );
}

const styl = StyleSheet.create({
  linki: { flexDirection: "row", gap: odstep.l, marginTop: odstep.xs },
  link: { color: kolory.indygo, fontWeight: "700" },
  pasekNaglowek: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  dzien: {
    width: 64,
    paddingVertical: odstep.s,
    borderRadius: promien.m,
    borderWidth: 1,
    borderColor: kolory.linia2,
    backgroundColor: kolory.powierzchnia,
    alignItems: "center",
    gap: 2,
  },
  dzienAktywny: { backgroundColor: kolory.indygo, borderColor: kolory.indygo },
  dzienBrak: { opacity: 0.45 },
  dzienNumer: { fontSize: 20, fontWeight: "700", color: kolory.tekst },
  siatka: { flexDirection: "row", flexWrap: "wrap", gap: odstep.s },
  slot: {
    minWidth: 76,
    paddingVertical: odstep.m,
    paddingHorizontal: odstep.m,
    borderRadius: promien.m,
    borderWidth: 1,
    borderColor: kolory.linia2,
    alignItems: "center",
    backgroundColor: kolory.powierzchnia,
  },
  slotAktywny: { backgroundColor: kolory.indygo, borderColor: kolory.indygo },
  slotTekst: { fontSize: 16, fontWeight: "600", color: kolory.tekst },
});
