/** Wspólne elementy interfejsu: ekran, karta, przycisk, pole, odznaka, komunikat. */
import type { PropsWithChildren, ReactNode } from "react";
import {
  ActivityIndicator,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { POLITYKA_PRYWATNOSCI } from "./api";
import { czcionka, kolory, odstep, promien } from "./theme";

/** Pociągnij w dół, żeby odświeżyć (telefon). W przeglądarce ekran daje własny przycisk. */
type Odswiezanie = { trwa: boolean; onOdswiez: () => void };

export function Ekran({ children, stopka, odswiezanie }: PropsWithChildren<{ stopka?: ReactNode; odswiezanie?: Odswiezanie }>) {
  return (
    <SafeAreaView style={styl.ekran} edges={["bottom", "left", "right"]}>
      <ScrollView
        contentContainerStyle={styl.tresc}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          odswiezanie ? (
            <RefreshControl
              refreshing={odswiezanie.trwa}
              onRefresh={odswiezanie.onOdswiez}
              tintColor={kolory.indygo}
              colors={[kolory.indygo]}
              title="Odświeżam..."
            />
          ) : undefined
        }
      >
        {children}
      </ScrollView>
      {stopka ? (
        <View style={styl.stopka}>
          <View style={styl.szerokosc}>{stopka}</View>
        </View>
      ) : null}
    </SafeAreaView>
  );
}

/** Błąd z przyciskiem ponowienia - dla braku sieci i chwilowej niedostępności serwera. */
export function BladZPonowieniem({ blad, onPonow, ladowanie }: { blad: string; onPonow: () => void; ladowanie?: boolean }) {
  return (
    <View style={{ gap: odstep.s }}>
      <Komunikat rodzaj="blad">{blad}</Komunikat>
      <Przycisk odmiana="drugi" onPress={onPonow} ladowanie={ladowanie}>
        Spróbuj ponownie
      </Przycisk>
    </View>
  );
}

export function Karta({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) {
  return <View style={[styl.karta, style]}>{children}</View>;
}

export function Tytul({ children }: PropsWithChildren) {
  return <Text style={czcionka.tytul}>{children}</Text>;
}

export function Naglowek({ children }: PropsWithChildren) {
  return <Text style={[czcionka.naglowek, { marginBottom: odstep.s }]}>{children}</Text>;
}

export function Pod({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) {
  return <Text style={[czcionka.pod, style]}>{children}</Text>;
}

type PrzyciskProps = PropsWithChildren<{
  onPress: () => void;
  odmiana?: "glowny" | "drugi" | "cichy" | "alarm";
  wylaczony?: boolean;
  ladowanie?: boolean;
  style?: StyleProp<ViewStyle>;
}>;

export function Przycisk({ children, onPress, odmiana = "glowny", wylaczony, ladowanie, style }: PrzyciskProps) {
  const nieaktywny = wylaczony || ladowanie;
  return (
    <Pressable
      onPress={onPress}
      disabled={nieaktywny}
      accessibilityRole="button"
      style={({ pressed }) => [
        styl.przycisk,
        odmiana === "glowny" && styl.przyciskGlowny,
        odmiana === "drugi" && styl.przyciskDrugi,
        odmiana === "cichy" && styl.przyciskCichy,
        odmiana === "alarm" && styl.przyciskAlarm,
        pressed && { opacity: 0.85 },
        nieaktywny && { opacity: 0.5 },
        style,
      ]}
    >
      {ladowanie ? (
        <ActivityIndicator color={odmiana === "glowny" || odmiana === "alarm" ? "#fff" : kolory.indygo} />
      ) : (
        <Text
          style={[
            styl.przyciskTekst,
            (odmiana === "drugi" || odmiana === "cichy") && { color: kolory.indygo },
          ]}
        >
          {children}
        </Text>
      )}
    </Pressable>
  );
}

type PoleProps = TextInputProps & { etykieta: string; blad?: string; pomoc?: string };

export function Pole({ etykieta, blad, pomoc, style, ...reszta }: PoleProps) {
  return (
    <View style={{ marginBottom: odstep.l }}>
      <Text style={styl.etykieta}>{etykieta}</Text>
      <TextInput
        placeholderTextColor={kolory.tekst2}
        style={[styl.pole, blad ? { borderColor: kolory.alarm } : null, style]}
        {...reszta}
      />
      {blad ? <Text style={styl.blad}>{blad}</Text> : pomoc ? <Text style={czcionka.maly}>{pomoc}</Text> : null}
    </View>
  );
}

/** Tekstowy odnośnik do strony albo mailto: (otwiera przeglądarkę / pocztę). */
export function Odnosnik({ children, adres }: PropsWithChildren<{ adres: string }>) {
  return (
    <Text style={styl.odnosnik} onPress={() => Linking.openURL(adres)} accessibilityRole="link">
      {children}
    </Text>
  );
}

/** Pod zgodą na przekazanie danych: gdzie przeczytać, co się z nimi dzieje. */
export function InformacjaPrywatnosc() {
  return (
    <Text style={czcionka.maly}>
      Jak przetwarzamy dane i jakie masz prawa: <Odnosnik adres={POLITYKA_PRYWATNOSCI}>polityka prywatności</Odnosnik>.
    </Text>
  );
}

export function Odznaka({ children, kolor = kolory.blekit }: PropsWithChildren<{ kolor?: string }>) {
  return (
    <View style={[styl.odznaka, { backgroundColor: kolor }]}>
      <Text style={styl.odznakaTekst}>{children}</Text>
    </View>
  );
}

export function Komunikat({ children, rodzaj = "info" }: PropsWithChildren<{ rodzaj?: "info" | "blad" | "sukces" }>) {
  const tlo = rodzaj === "blad" ? kolory.alarmTlo : rodzaj === "sukces" ? kolory.sukcesTlo : kolory.info;
  const kolor = rodzaj === "blad" ? kolory.alarm : rodzaj === "sukces" ? kolory.sukces : kolory.tekst;
  return (
    <View style={[styl.komunikat, { backgroundColor: tlo }]} accessibilityLiveRegion="polite">
      <Text style={[czcionka.tekst, { color: kolor }]}>{children}</Text>
    </View>
  );
}

export function Ladowanie({ tekst = "Wczytuję..." }: { tekst?: string }) {
  return (
    <View style={{ padding: odstep.xxl, alignItems: "center", gap: odstep.m }}>
      <ActivityIndicator color={kolory.indygo} size="large" />
      <Text style={czcionka.pod}>{tekst}</Text>
    </View>
  );
}

export function Zaznaczenie({
  zaznaczone,
  onChange,
  children,
}: PropsWithChildren<{ zaznaczone: boolean; onChange: (v: boolean) => void }>) {
  return (
    <Pressable
      onPress={() => onChange(!zaznaczone)}
      accessibilityRole="checkbox"
      accessibilityState={{ checked: zaznaczone }}
      style={styl.zaznaczenie}
    >
      <View style={[styl.kratka, zaznaczone && { backgroundColor: kolory.indygo, borderColor: kolory.indygo }]}>
        {zaznaczone ? <Text style={{ color: "#fff", fontWeight: "700", fontSize: 14 }}>✓</Text> : null}
      </View>
      <Text style={[czcionka.pod, { flex: 1, color: kolory.tekst }]}>{children}</Text>
    </Pressable>
  );
}

export function Wybor<T extends string>({
  opcje,
  wartosc,
  onChange,
}: {
  opcje: readonly T[];
  wartosc: T | "";
  onChange: (v: T) => void;
}) {
  return (
    <View style={styl.wybor}>
      {opcje.map((o) => {
        const aktywna = o === wartosc;
        return (
          <Pressable
            key={o}
            onPress={() => onChange(o)}
            accessibilityRole="radio"
            accessibilityState={{ selected: aktywna }}
            style={[styl.chip, aktywna && styl.chipAktywny]}
          >
            <Text style={[styl.chipTekst, aktywna && { color: "#fff" }]}>{o}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export const styl = StyleSheet.create({
  ekran: { flex: 1, backgroundColor: kolory.tlo },
  // Na szerokim ekranie (przeglądarka na komputerze, tablet) treść nie rozlewa się na całą szerokość.
  szerokosc: { width: "100%", maxWidth: 640, alignSelf: "center" },
  tresc: { padding: odstep.l, paddingBottom: odstep.xxl, gap: odstep.l, width: "100%", maxWidth: 672, alignSelf: "center" },
  stopka: {
    padding: odstep.l,
    borderTopWidth: 1,
    borderTopColor: kolory.linia,
    backgroundColor: kolory.powierzchnia,
  },
  karta: {
    backgroundColor: kolory.powierzchnia,
    borderRadius: promien.l,
    padding: odstep.l,
    borderWidth: 1,
    borderColor: kolory.linia,
    gap: odstep.s,
  },
  przycisk: {
    minHeight: 48,
    borderRadius: promien.m,
    paddingHorizontal: odstep.l,
    alignItems: "center",
    justifyContent: "center",
  },
  przyciskGlowny: { backgroundColor: kolory.indygo },
  przyciskDrugi: { backgroundColor: kolory.powierzchnia, borderWidth: 1, borderColor: kolory.indygo },
  przyciskCichy: { backgroundColor: "transparent" },
  przyciskAlarm: { backgroundColor: kolory.alarm },
  przyciskTekst: { color: "#fff", fontSize: 16, fontWeight: "700" },
  etykieta: { ...czcionka.pod, marginBottom: odstep.xs, color: kolory.tekst },
  pole: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: kolory.linia2,
    borderRadius: promien.m,
    paddingHorizontal: odstep.m,
    paddingVertical: odstep.s,
    fontSize: 16,
    color: kolory.tekst,
    backgroundColor: kolory.powierzchnia,
  },
  blad: { ...czcionka.maly, color: kolory.alarm, marginTop: odstep.xs },
  odznaka: { alignSelf: "flex-start", borderRadius: 999, paddingHorizontal: odstep.m, paddingVertical: 3 },
  odznakaTekst: { color: "#fff", fontSize: 12, fontWeight: "700" },
  komunikat: { borderRadius: promien.m, padding: odstep.m },
  odnosnik: { color: kolory.indygo, fontWeight: "600", textDecorationLine: "underline" },
  zaznaczenie: { flexDirection: "row", gap: odstep.m, alignItems: "flex-start", paddingVertical: odstep.s },
  kratka: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: kolory.linia2,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: kolory.powierzchnia,
  },
  wybor: { flexDirection: "row", flexWrap: "wrap", gap: odstep.s },
  chip: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: kolory.linia2,
    paddingHorizontal: odstep.m,
    paddingVertical: odstep.s,
    backgroundColor: kolory.powierzchnia,
  },
  chipAktywny: { backgroundColor: kolory.indygo, borderColor: kolory.indygo },
  chipTekst: { fontSize: 14, color: kolory.tekst },
});
