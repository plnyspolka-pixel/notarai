import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { kolory } from "../src/theme";

export default function Uklad() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: kolory.granat },
          headerTintColor: "#fff",
          headerTitleStyle: { fontWeight: "700" },
          headerBackButtonDisplayMode: "minimal",
          contentStyle: { backgroundColor: kolory.tlo },
        }}
      >
        <Stack.Screen name="index" options={{ title: "notarai" }} />
        <Stack.Screen name="kancelarie" options={{ title: "Kancelarie" }} />
        <Stack.Screen name="kancelaria/[id]" options={{ title: "Wolne terminy" }} />
        <Stack.Screen name="rezerwacja" options={{ title: "Rezerwacja wizyty" }} />
        <Stack.Screen name="potwierdzenie" options={{ title: "Wizyta umówiona", headerBackVisible: false }} />
        <Stack.Screen name="zapytanie" options={{ title: "Zapytanie o termin" }} />
        <Stack.Screen name="wizyty" options={{ title: "Moje wizyty" }} />
        <Stack.Screen name="o-aplikacji" options={{ title: "O aplikacji" }} />
      </Stack>
    </>
  );
}
