# NotarAI - Google Calendar

## Dzialanie

- Dwukierunkowa synchronizacja wizyt z glownym kalendarzem Google (primary). Tworzenie, przesuwanie i usuwanie pojedynczych terminow dziala w obu kierunkach.
- Automatyczny worker w SaaS: co 5 minut, takze przy zamknietej przegladarce, oraz reczne "Synchronizuj teraz". Wylacznik PIECZAPP_GOOGLE_KALENDARZ_AUTO=0.
- Jedna kancelaria ma odrebne mapowania i sekret OAuth. Operacje laczenia i odlaczania wykonuje tylko wlasciciel (nie serwis ani pomocnik).
- Google widzi jedynie neutralny tytul "Zajete - NotarAI", godzine i techniczny identyfikator. Nazwiska, telefony, sygnatury i opisy nie opuszczaja NotarAI. Z Google zapisujemy w NotarAI tylko blokade "Zajete w Google" i czas.
- Konflikty dwustronnych edycji i zajetosci nie sa rozstrzygane przez ciche nadpisanie: wymagaja recznego przegladu.
- OAuth 2.0: podpisany, jednorazowy state, PKCE; refresh token i weryfikator PKCE sa w Secrets Manager, lokalnie tylko w pamieci procesu.

## Wymagania produkcyjne

1. W Google Cloud wlacz Google Calendar API i skonfiguruj ekran zgody z zakresem calendar.events, openid, email. Google moze wymagac weryfikacji OAuth.
2. Dodaj redirect URI https://<ADRES-APLIKACJI>/api/google-kalendarz/powrot do istniejacego klienta OAuth dla NotarAI. To osobny URI od poczty: /api/korespondencja/oauth/powrot.
3. Ustaw PIECZAPP_ADRES na publiczny adres HTTPS; PIECZAPP_OAUTH_GOOGLE_KLIENT i PIECZAPP_OAUTH_GOOGLE_SEKRET pochodza z istniejacego sekretu notarai/oauth-poczty (CloudFormation OAuthPocztySekretArn).
4. Wdroz IAM z infra/notarai-aplikacja.yaml dla sekretow notarai-google-kalendarz-* we Frankfurcie. W SaaS wymagana stabilna wartosc PIECZAPP_ADMIN_TOKEN do podpisywania state.
5. Otworz Kalendarz w NotarAI i polacz konto Google. Zrob test fikcyjnymi danymi: utworzenie, zmiana, usuniecie, konflikt i rozlaczenie; zweryfikuj brak PII w Google i logach.

## Ograniczenia

- Jedno konto i jeden kalendarz primary na kancelarie. Nie ma wyboru kalendarza pracownika.
- Horyzont: ostatnie 30 dni i nastepne 365 dni. Wydarzenia wielodniowe (poza jednodniowa blokada calodniowa) sa pomijane. Calodniowa blokada mapowana na 08:30-18:00.
- Google recurring events sa rozwijane do pojedynczych wystapien. Zmiany wystapienia moga utworzyc wyjatek w serii.
- Celowo nie importujemy tytulow/uczestnikow Google ani nie eksportujemy danych spraw z NotarAI.
- Synchronizacja okresowa bez webhookow Google; dla bardzo duzych kalendarzy kolejnym etapem sa syncToken i events.watch.
- Odłączenie usuwa zaimportowane blokady Google z NotarAI i czysci token, ale nie usuwa wydarzen w Google.
- Kancelarie w trybie przechowywania "u-klienta" nie korzystaja z serwerowej integracji.

## Testy

pytest -q test_google_kalendarz.py test_kalendarz.py test_kalendarz_ui.py

Do testow na zywo potrzebne sa uprawnienia Google Cloud i testowe konto; nie uzywac prawdziwych danych aktow.
