# Agent głosowy notarai (ElevenLabs)

Asystentka „Ola” obsługuje dwie grupy rozmówców:
- **klientów kancelarii**: koszt czynności (taksa.py), dokumenty, kancelarie
  w miejscowości (neutralna kolejność jak na stronie), wolne godziny, rezerwacja
  online albo prośba o kontakt,
- **kancelarie**: pytania o notarai (cena, RODO, funkcje) i prośba o kontakt
  zespołu notarai.

## Gdzie co jest
| Element | Miejsce |
|---|---|
| Webhooki narzędzi | `agent_glosowy.py` → `POST /api/agent-glosowy/<narzędzie>` |
| Testy | `test_agent_glosowy.py` |
| Prompt agenta (kopia wersjonowana) | `docs/agent-glosowy/prompt.md` |
| Baza wiedzy (kopia wersjonowana) | `docs/agent-glosowy/baza-wiedzy.md` |
| Token webhooków (opcjonalny) | sekret `notarai/agent-glosowy` → `PIECZAPP_AGENT_GLOSOWY_TOKEN`, skrypt `infra/zapisz-sekret-agenta-glosowego.ps1` |

## ElevenLabs
- Agent: `agent_5501m7611p1nfarsk1k4x9h49bhk` („notarai — asystentka głosowa Ola”), język pl,
  LLM claude-sonnet-4-6, strefa Europe/Warsaw, głos `8EWWaNTDrqObI22Gvo1q`.
- Baza wiedzy: `TgZJyH1K9d7ALS1vPlBu`.
- Sekret nagłówka `X-Notarai-Agent`: `notarai_agent_glosowy_token` (`m7LyXuWa80Xqs9Dll4UY`).
- Narzędzia (webhook, POST na https://app.notarai.pl/api/agent-glosowy/...):

| Narzędzie | ID | Trasa |
|---|---|---|
| notarai_koszt | tool_8701m760wjfpezzbgsdmsyfwca09 | /koszt |
| notarai_dokumenty | tool_9801m760ymj5ersr7d23cvkpg2jg | /dokumenty |
| notarai_kancelarie | tool_2301m760ynavewvtksde6abdpfq8 | /kancelarie |
| notarai_terminy | tool_7901m760ypb7er18dp3c4ygdrpny | /terminy |
| notarai_rezerwacja | tool_1501m760yqw8f9cb0twp4k5bcbw4 | /rezerwacja |
| notarai_zgloszenie | tool_5601m760yrj7frrrznf2pp81dkqx | /zgloszenie |
| notarai_kontakt_kancelarii | tool_7901m760ys93eje91wn7hsnbe242 | /kontakt-notarai |

Każde narzędzie wysyła `rozmowa` = `system__conversation_id` - po nim liczone są
limity (domyślnie 60 odczytów i 3 zapisy na rozmowę, 5000/200 na dobę;
zmienne `PIECZAPP_AGENT_GLOSOWY_*`). Błędy, które rozmówca może poprawić,
wracają jako `{"ok": false, "do_powiedzenia": "..."}` (HTTP 200), bo ElevenLabs
inaczej ukrywa treść błędu przed modelem.

Zmiana promptu: edytuj `prompt.md`, a potem tę samą treść w ElevenLabs
(agent → Agent → System prompt) - plik jest źródłem prawdy.

## Dostęp i RODO
- Trasy `/api/agent-glosowy` są otwarte jak publiczne formularze strony
  (`/api/taksa`, `/api/wizyty`), które robią to samo. Po uruchomieniu
  `infra/zapisz-sekret-agenta-glosowego.ps1` i wdrożeniu wymagają tokenu.
- Do logów aplikacji trafiają tylko nazwy narzędzi, liczby i identyfikatory
  zgłoszeń. Agent nie zbiera PESEL, adresów nieruchomości ani numerów KW
  (prompt) - kancelaria dostaje imię, kontakt i krótki opis sprawy, tak jak
  z formularza strony.
- ElevenLabs przechowuje transkrypcje rozmów (ustawienie retencji w agencie).
  ElevenLabs jest dalszym odbiorcą danych z rozmowy - patrz `docs/czeka-na-dostep.md` NA-7
