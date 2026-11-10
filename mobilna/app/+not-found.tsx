/** Nieznany adres (np. stary link w przeglądarce): po polsku i z drogą do startu. */
import { router, Stack } from "expo-router";
import { Ekran, Komunikat, Przycisk } from "../src/ui";

export default function NieZnaleziono() {
  return (
    <Ekran>
      <Stack.Screen options={{ title: "Nie ma takiej strony" }} />
      <Komunikat>Ten adres nie prowadzi do żadnego ekranu aplikacji notarai.</Komunikat>
      <Przycisk onPress={() => router.replace("/")}>Znajdź notariusza</Przycisk>
      <Przycisk odmiana="drugi" onPress={() => router.replace("/wizyty")}>
        Moje wizyty
      </Przycisk>
    </Ekran>
  );
}
