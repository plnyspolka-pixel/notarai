/**
 * Wizyty klienta zapisane w telefonie. Aplikacja nie ma konta ani logowania:
 * dowodem własności rezerwacji jest token z odpowiedzi serwera, trzymany tylko
 * tutaj. Usunięcie aplikacji usuwa tokeny - wizyta w kancelarii zostaje,
 * a odwołać ją można wtedy telefonicznie.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { Rezerwacja } from "./api";

const KLUCZ = "notarai.wizyty.v1";

export type Wizyta = Rezerwacja & { token: string; zapisano: string };

export async function wczytajWizyty(): Promise<Wizyta[]> {
  try {
    const surowe = await AsyncStorage.getItem(KLUCZ);
    const lista = surowe ? (JSON.parse(surowe) as Wizyta[]) : [];
    return lista.sort((a, b) => (a.data + a.godzina).localeCompare(b.data + b.godzina));
  } catch {
    return [];
  }
}

async function zapiszListe(lista: Wizyta[]): Promise<void> {
  await AsyncStorage.setItem(KLUCZ, JSON.stringify(lista));
}

/** Dodaje albo podmienia wizytę (po id). Token z pierwszego zapisu zostaje. */
export async function zapiszWizyte(r: Rezerwacja, token?: string): Promise<Wizyta> {
  const lista = await wczytajWizyty();
  const stara = lista.find((w) => w.id === r.id);
  const nowa: Wizyta = {
    ...stara,
    ...r,
    token: token ?? r.token ?? stara?.token ?? "",
    zapisano: stara?.zapisano ?? new Date().toISOString(),
  };
  delete (nowa as { komunikat?: string }).komunikat;
  await zapiszListe([...lista.filter((w) => w.id !== r.id), nowa]);
  return nowa;
}

export async function usunWizyte(id: string): Promise<void> {
  const lista = await wczytajWizyty();
  await zapiszListe(lista.filter((w) => w.id !== id));
}

export async function znajdzWizyte(id: string): Promise<Wizyta | undefined> {
  return (await wczytajWizyty()).find((w) => w.id === id);
}
