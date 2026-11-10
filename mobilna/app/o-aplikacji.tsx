/** O aplikacji: wersja, kto ją prowadzi, kontakt, prywatność. */
import Constants from "expo-constants";
import { Platform, Text } from "react-native";
import { API_URL, KONTAKT_EMAIL, linkEmail, POLITYKA_PRYWATNOSCI, STRONA } from "../src/api";
import { czcionka } from "../src/theme";
import { Ekran, Karta, Naglowek, Odnosnik, Pod } from "../src/ui";

export default function OAplikacji() {
  const wersja = Constants.expoConfig?.version ?? "–";
  const platforma = Platform.OS === "web" ? "przeglądarka" : Platform.OS === "ios" ? "iOS" : "Android";
  return (
    <Ekran>
      <Karta>
        <Naglowek>notarai – wizyta u notariusza</Naglowek>
        <Pod>
          Wybierasz kancelarię i wolną godzinę, potwierdzasz numer telefonu kodem SMS, a wizyta trafia od razu do
          kalendarza kancelarii. Dzień przed wizytą przypominamy SMS-em. Bez zakładania konta.
        </Pod>
        <Text style={czcionka.maly}>
          Wersja {wersja} · {platforma}
          {API_URL !== "https://app.notarai.pl" ? ` · serwer ${API_URL}` : ""}
        </Text>
      </Karta>

      <Karta>
        <Naglowek>Kontakt</Naglowek>
        <Pod>Pytania o aplikację, błędy, propozycje:</Pod>
        <Odnosnik adres={linkEmail(KONTAKT_EMAIL, "Aplikacja notarai")}>{KONTAKT_EMAIL}</Odnosnik>
        <Pod>
          W sprawie samej wizyty (dokumenty, koszt, zmiana terminu) najszybciej pomoże kancelaria – jej telefon jest przy
          wizycie.
        </Pod>
      </Karta>

      <Karta>
        <Naglowek>Prywatność</Naglowek>
        <Pod>
          Imię, telefon, e-mail i uwagi trafiają wyłącznie do kalendarza wybranej kancelarii, która jest ich
          administratorem. Weryfikację numeru (numer i kod SMS) serwer zapisuje tylko jako skróty kryptograficzne. Lokalizacji
          używamy jedynie po kliknięciu „Najbliżej mnie” i nie zapisujemy jej. Aplikacja nie ma reklam ani analityki.
        </Pod>
        <Odnosnik adres={POLITYKA_PRYWATNOSCI}>Polityka prywatności</Odnosnik>
        <Odnosnik adres={`${STRONA}/regulamin/`}>Regulamin</Odnosnik>
      </Karta>

      <Text style={[czcionka.maly, { textAlign: "center" }]}>
        Usługę notarai.pl prowadzi Fundacja Krzewienia Edukacji Finansowej im. Pieczaka, ul. Wilhelma Orlika Ruckemana 4/18,
        20-244 Lublin, KRS 0001140846.
      </Text>
      <Text style={[czcionka.maly, { textAlign: "center" }]}>
        <Odnosnik adres={STRONA}>notarai.pl</Odnosnik>
      </Text>
    </Ekran>
  );
}
