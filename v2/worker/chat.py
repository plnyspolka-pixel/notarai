"""Chat-first front door. The notary types a sentence; this module decides what to do.

Routing is deterministic for anything that changes state (copies, devices, settings): a fixed
set of Polish phrasings, never a model's guess. Only what is left over, a question about the
case, goes to the model. Irreversible actions return a confirmation the user must tap.

A reply is a list of blocks the page renders: text, buttons (which send a sentence back),
documents, a draft to approve, a one-time secret, a QR code, a sign-in form, a confirmation.
"""
import base64
import os
import re
import secrets
import time
import unicodedata
from decimal import Decimal, InvalidOperation

from .drafting import DraftError
from .layout import tools_for
from .autofill import FillError
from .mail import MailError, as_document
from .rules import RuleViolation
from .vault import valid_case

DRAFT_WORDS = ("przygotuj", "napisz", "sporzadz", "zredaguj", "stworz projekt", "projekt aktu", "projekt umowy")
CONFIRM_TTL = 300


def norm(text: str) -> str:
    text = text.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").strip()


def text(message: str) -> dict:
    return {"type": "text", "text": message}


def buttons(*items) -> dict:
    return {"type": "buttons", "items": [{"label": label, "say": say} for label, say in items]}


def parse_amount(message: str) -> Decimal | None:
    """'500 tys.', '1,2 mln zł', '350000', '350 000,50 zł'."""
    found = re.search(r"(\d[\d \u00a0.]*(?:,\d+)?)\s*(mln|milion\w*|tys\w*|k\b)?", message.lower())
    if not found:
        return None
    number = found.group(1).replace(" ", "").replace("\u00a0", "")
    number = number.replace(".", "") if found.group(2) is None or "," in number else number
    try:
        value = Decimal(number.replace(",", "."))
    except InvalidOperation:
        return None
    unit = found.group(2) or ""
    if unit.startswith(("mln", "milion")):
        value *= 1_000_000
    elif unit.startswith(("tys", "k")):
        value *= 1_000
    return value if value > 0 else None


def understood(answer: str) -> tuple[str, str | None]:
    """(answer without it, the assistant's own one-line understanding) from a leading „ROZUMIEM:” line."""
    lines = answer.lstrip().splitlines()
    if lines and re.match(r"\s*\**ROZUMIEM\**\s*:", lines[0], re.I):
        return "\n".join(lines[1:]).lstrip(), re.sub(r"^\s*\**ROZUMIEM\**\s*:\s*", "", lines[0], flags=re.I).strip()
    return answer, None


def answer_blocks(answer: str) -> list[dict]:
    """The assistant's answer, with its „DALEJ:” line turned into next-step buttons."""
    answer, _ = understood(answer)
    lines = answer.rstrip().splitlines()
    steps = []
    while lines and re.match(r"\s*\**DALEJ\**\s*:", lines[-1], re.I):
        raw = re.sub(r"^\s*\**DALEJ\**\s*:\s*", "", lines.pop(), flags=re.I)
        steps = [s.strip(" „”\"*.-") for s in raw.split("|") if s.strip(" „”\"*.-")][:3]
    blocks = [text("\n".join(lines).strip())]
    if steps:
        blocks.append(text("Proponuję dalej:"))
        blocks.append(buttons(*[(step[:60], step) for step in steps]))
    return blocks


def when(ns: int) -> str:
    stamp = time.localtime(ns // 10**9)
    today = time.localtime()
    day = "dziś" if stamp[:3] == today[:3] else time.strftime("%d.%m", stamp)
    return f"{day} o {time.strftime('%H:%M', stamp)}"


class Chat:
    def __init__(self, services):
        self.s = services
        self._pending: dict[str, tuple[str, float, callable]] = {}
        self._inbox: dict[str, list] = {}       # last listing per identity, in memory only
        self._sheets: dict[tuple, dict] = {}    # last values per (identity, case, procedure), for „wpisz ponownie”
        self._agendas: dict[str, list] = {}     # last calendar listing per identity, for „usuń termin 2”
        self._lessons: dict[str, list] = {}     # last lessons listing per identity, for „zapomnij lekcję 3”
        self._replies: dict[str, tuple] = {}    # the last reply draft per identity, for „wyślij”
        self._read_messages: dict[str, int] = {}  # when each identity last looked at the messenger

    # ------------------------------------------------------------ confirmations
    def _confirm(self, identity, question: str, label: str, action, *, explicit: bool = True) -> dict:
        """Owner's decision 27.11.2026: an explicit command is the approval, so it runs at once. The
        "Tak / Nie" step comes back with the setting `confirm`, or when the command did not ask for
        this action itself (e.g. sending a form after „wypełnij”, without „wyślij”)."""
        if explicit and not self.s.settings().confirm:
            return {"type": "now", "blocks": action()}
        now = time.monotonic()
        self._pending = {k: v for k, v in self._pending.items() if v[1] > now}
        token = secrets.token_urlsafe(16)
        self._pending[token] = (identity.id, now + CONFIRM_TTL, action)
        return {"type": "confirm", "text": question, "label": label, "token": token}

    def confirm(self, identity, token: str) -> list[dict]:
        owner, expires, action = self._pending.get(token, ("", 0, None))
        if owner == identity.id:
            self._pending.pop(token, None)      # only its owner can use up a confirmation
        if action is None or owner != identity.id or expires <= time.monotonic():
            return [text("To potwierdzenie wygasło. Napisz polecenie jeszcze raz.")]
        return self._flatten(action())

    # ------------------------------------------------------------ entry points
    def hello(self, identity, case) -> list[dict]:
        admin = identity.scope == "admin"
        blocks = [text("Dzień dobry. Napisz, co mam zrobić, albo wybierz podpowiedź." if not admin else
                       "Dzień dobry. Tu ustawiasz to stanowisko. Napisz, co mam zrobić, albo wybierz podpowiedź.")]
        blocks += self._warnings(admin)
        today = self.s.calendar.upcoming(1, cases=identity.cases) if identity.scope != "listen" else []
        if today:
            blocks.append(text("Dziś: " + "; ".join(f"{e['label'].split()[-1]} {e['title']}" for e in today[:6]) + "."))
        if admin and self.s.program.current is not None and self.s.program.ready_version():
            blocks.append(text(f"Gotowa aktualizacja programu do wersji {self.s.program.ready_version()}."))
            blocks.append(buttons(("Uruchom ponownie i zaktualizuj", "zainstaluj aktualizację")))
        step = self.s.onboarding.current() if admin else None
        if step is not None:
            if step["number"] == 1:
                blocks.append(text("Witaj w NotarAI. Przeprowadzę Cię przez pierwsze uruchomienie: kilka krótkich kroków. "
                                   "Najpierw sprawdziłem, co jest na tym komputerze, żeby od razu podłączyć to, czego używasz."
                                   if self.s.program.current is not None else
                                   "Witaj w NotarAI. Przeprowadzę Cię przez pierwsze uruchomienie: kilka krótkich kroków, "
                                   "większość możesz pominąć i wrócić do niej później."))
                if step["key"] == "rozpoznanie" and self.s.program.current is not None:
                    # An installed program looks around by itself: the first screen already shows what was found.
                    blocks += self._environment(refresh=True)
                    step = self.s.onboarding.current()
                    if step is None:
                        return blocks
            offered = {say for _, say in step["actions"]}        # the guide offers it: no second button
            blocks = [b for b in blocks if b["type"] != "buttons" or not {i["say"] for i in b["items"]} <= offered]
            return blocks + self._guide_card(step)
        offered = {i["say"] for b in blocks if b["type"] == "buttons" for i in b["items"]}
        ahead = [i for i in self.suggestions(identity, case) if i["say"] not in offered]
        if ahead:
            blocks.append(text("Proponuję teraz: " + "; ".join(f"{i['label']} ({i['why']})" for i in ahead) + "."))
            blocks.append(buttons(*[(i["label"], i["say"]) for i in ahead]))
        if admin:
            blocks.append(buttons(("Stan stanowiska", "stan"), ("Gdzie są dane", "gdzie są dane"), ("Dodaj telefon", "dodaj telefon"),
                                  ("Zrób kopię", "zrób kopię"), ("Kto czytał dokumenty?", "dziennik"),
                                  ("Dokumenty", "dokumenty"), ("Co umiesz?", "pomoc")))
        else:
            blocks.append(buttons(("Dokumenty", "dokumenty"), ("Sprawy", "sprawy"),
                                  ("Policz taksę", "taksa"), ("Co umiesz?", "pomoc")))
        return blocks

    @staticmethod
    def _flatten(blocks) -> list[dict]:
        out = []
        for block in blocks:
            out += Chat._flatten(block["blocks"]) if block.get("type") == "now" else [block]
        return out

    def say(self, identity, message: str, case, names) -> list[dict]:
        return self._flatten(self._say(identity, message, case, names))

    def _say(self, identity, message: str, case, names) -> list[dict]:
        message = " ".join(message.split())
        plain = norm(message)
        self._plain = plain
        admin = identity.scope == "admin"
        before = self.s.onboarding.current() if admin else None
        reply = self._route(identity, message, plain, case, names)
        return self._flatten(reply) + (self._guide_progress(before) if admin else [])

    def _route(self, identity, message: str, plain: str, case, names) -> list[dict]:
        admin = identity.scope == "admin"
        office_rules = self._office_rules(identity, message, plain)
        if office_rules is not None:
            return office_rules
        tiles = self._tiles(identity, message, plain)       # first: a tile may be named after any command
        if tiles is not None:
            return tiles
        together = self._office(identity, message, plain, case)
        if together is not None:
            return together
        taught = self._learning(identity, message, plain)
        if taught is not None:
            return taught
        checked = self._registers(identity, message, plain, case)
        if checked is not None:
            return checked
        planned = self._calendar(identity, message, plain, case, identity.scope in {"admin", "write"})
        if planned is not None:        # before the panel: "usuń termin 2" is not a device called "termin 2"
            return planned
        if admin:
            reply = self._admin(identity, message, plain, case)
            if reply is not None:
                return reply
        return self._common(identity, message, plain, case, names)

    def _guide_progress(self, before) -> list[dict]:
        """After a turn: when the step that was current is now done, say so and show the next one."""
        if before is None or not self.s.onboarding.done(before["key"]):
            return []
        following = self.s.onboarding.current()
        if following is None:
            return [text(f"✓ {before['title']}. To był ostatni krok przewodnika: stanowisko jest gotowe. "
                         "Listę zawsze zobaczysz, pisząc „przewodnik”.")]
        return [text(f"✓ {before['title']}.")] + self._guide_card(following)

    # ------------------------------------------------------------ shared intents
    def _common(self, identity, message, plain, case, names) -> list[dict]:
        s, writable = self.s, identity.scope in {"admin", "write"}
        if plain in {"pokaz mozliwosci", "mozliwosci", "co potrafi notarai", "co mozesz dla mnie zrobic", "pokaz"}:
            from .tour import slides
            return [{"type": "tour", "slides": slides(), "done": "pokaz obejrzany"}]
        if plain == "pokaz obejrzany":
            if identity.scope == "admin":
                s.onboarding.mark("mozliwosci")
            return [text("Wszystkie możliwości są też w „Co umiesz?” i zawsze możesz napisać „pokaż możliwości”.")]
        if plain in {"pomoc", "help", "co umiesz", "co umiesz?", "co potrafisz", "co potrafisz?"}:
            return self._help(identity.scope == "admin", writable) + [buttons(("Pokaż możliwości", "pokaż możliwości"))]
        learned = self._procedures(identity, message, plain, case, names, writable)
        if learned is not None:
            return learned
        if plain in {"sprawy", "lista spraw", "pokaz sprawy", "jakie sa sprawy", "jakie sa sprawy?"}:
            cases = s.cases(identity)
            if not cases:
                return [text("Nie ma jeszcze żadnej sprawy. Napisz „nowa sprawa” i jej nazwę, np. „nowa sprawa kowalski-2026”.")]
            return [text("Którą sprawę otworzyć?"), buttons(*[(c, f"sprawa {c}") for c in cases[:30]])]
        found = re.fullmatch(r"(?:nowa sprawa|sprawa|przejdz do sprawy|otworz sprawe|przejdz do)\s+(\S+)", plain)
        if found:
            name = message.split()[-1]
            if not valid_case(name) or not s.may_see_case(identity, name):
                return [text("Nazwa sprawy może mieć litery, cyfry, myślnik i kropkę, bez spacji.")]
            return [{"type": "case", "case": name}, text(f"Sprawa „{name}”. Co robimy?"),
                    buttons(("Dokumenty", "dokumenty"), ("Przygotuj projekt", "przygotuj projekt umowy"))]
        if plain.startswith(("strony:", "strony ", "osoby:")):
            listed = [n.strip() for n in re.split(r"[,;\n]", message.split(":", 1)[-1] if ":" in message
                                                  else message.split(" ", 1)[-1]) if n.strip()][:50]
            if case is None or not s.may_see_case(identity, case):
                return [text("Najpierw wybierz sprawę, której dotyczą te osoby.")]
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            listed = s.vault.set_parties(case, listed)
            return [{"type": "names", "names": listed},
                    text(f"Zapamiętałem strony sprawy „{case}”: " + ", ".join(listed) + "."
                         + (" Model zobaczy je jako znaczniki, na każdym urządzeniu." if s.pseudonymizes() else ""))]
        if re.search(r"\b(dokumenty|pliki|lista dokumentow|co jest w sprawie|pokaz dokumenty)\b", plain) \
                and not plain.startswith(DRAFT_WORDS):
            return self._documents(identity, case)
        if "taks" in plain or plain.startswith(("ile kosztuje", "koszt ", "policz koszt")):
            return self._fee(message, plain)
        found = re.fullmatch(r"(?:notatka|zapisz notatke|zanotuj)\s*:?\s*(.+)", message, re.IGNORECASE | re.DOTALL)
        if found and norm(message).startswith(("notatka", "zapisz notatke", "zanotuj")):
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            if not s.may_see_case(identity, case):
                return [text("Najpierw wybierz sprawę.")]
            name = time.strftime("notatka-%Y%m%d-%H%M%S.txt")
            doc_id, version = s.vault.put(None, 0, name, found.group(1).encode(), actor=identity.id, case=case)
            return [text(f"Zapisałem notatkę jako {name}."),
                    {"type": "documents", "items": [{"id": doc_id, "name": name, "version": version}]}]
        found = re.fullmatch(r"(?:przepisz|spisz|odsluchaj|transkrybuj)(?: nagranie| notatke)?\s+(.+)", plain)
        if found:
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            match = self._find_document(identity, case, found.group(1))
            if not isinstance(match, dict):
                return [text("Które nagranie przepisać?")] + ([{"type": "documents", "items": match}] if match else [])
            result = s.transcribe_document(match["id"], identity.id)
            if result["text"]:
                return [text("Przepisałem nagranie:\n\n" + result["text"]), {"type": "documents", "items": result["documents"]}]
            return [text(result["detail"])]
        found = re.fullmatch(r"(?:stresc|streszcz|podsumuj|przeczytaj|co jest w|co zawiera|sprawdz)\s+(?:plik\s+|dokument\s+)?(.+)", plain)
        if found:
            match = self._find_document(identity, case, found.group(1))
            if isinstance(match, dict) and match["name"].lower().endswith((".txt", ".docx", ".eml", ".pdf")):
                if plain.startswith("sprawdz"):
                    question = ("Sprawdź ten dokument jak notariusz: błędy, niespójności (nazwiska, kwoty, daty, "
                                "numery KW), braki i ryzyka. Wypunktuj krótko.")
                else:
                    question = ("Streść ten dokument dla notariusza w kilku punktach: rodzaj dokumentu, strony, "
                                "przedmiot, kwoty, terminy, czego brakuje albo co budzi wątpliwość.")
                s.narrate(identity, f"Czytam {match['name']} i " + ("szukam błędów i niespójności." if plain.startswith("sprawdz") else "przygotowuję streszczenie."))
                answer = s.drafts.ask(match["case"], question, identity.id, names, document=match["id"])
                answer["answer"] = answer_blocks(answer["answer"])[0]["text"] if "DALEJ" in answer["answer"] else answer["answer"]
                return [text(f"{match['name']}:\n\n" + answer["answer"]),
                        buttons(("Sprawdź błędy", f"sprawdź {match['name']}"), ("Otwórz", f"otwórz {match['name']}"))]
            if isinstance(match, dict):
                return [text("Ten plik zapisałem, ale nie umiem go przeczytać (czytam DOCX, PDF z tekstem, TXT i e-mail; "
                             "nagrania przepisuję).")]
            if match:
                return [text("Który dokument?"), {"type": "documents", "items": match}]
        found = re.fullmatch(r"(?:otworz|pokaz|wyswietl)\s+(.+)", plain)
        if found:
            match = self._find_document(identity, case, found.group(1))
            if isinstance(match, dict):
                return [{"type": "open", "id": match["id"]}, text(f"Otwieram {match['name']}.")]
            if match:
                return [text("Który dokument?"), {"type": "documents", "items": match}]
        if case is None:
            if plain.startswith(DRAFT_WORDS):
                return [text("Do której sprawy? Wybierz sprawę u góry albo napisz „nowa sprawa” i jej nazwę."),
                        buttons(("Sprawy", "sprawy"))]
            # No case chosen: the same chat answers as a general assistant, without reading any documents.
            s.narrate(identity, "Rozumiem to jako pytanie ogólne, bez konkretnej sprawy: nie czytam żadnych dokumentów.")
            s.narrate(identity, "Pytam asystenta we Frankfurcie" + ("; nazwiska i numery zamieniam na znaczniki." if s.pseudonymizes() else "."))
            said = s.general(message, names)["answer"]
            line = understood(said)[1]
            if line:
                s.narrate(identity, "Jak to rozumiem: " + line)
            return answer_blocks(said)
        if not s.may_see_case(identity, case):
            return [text("Nie ma takiej sprawy.")]
        if plain.startswith(DRAFT_WORDS) or " projekt " in f" {plain} ":
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu, więc nie przygotuje projektu.")]
            count = len(s.documents(identity, case))
            s.narrate(identity, f"Rozumiem: projekt dokumentu w sprawie „{case}”. Czytam jej dokumenty ({count}).")
            s.narrate(identity, "Dobieram sformułowania kancelarii, wymagane zdania z zasad i to, czego nauczyłem się z Twoich poprawek.")
            s.narrate(identity, "Piszę projekt z asystentem we Frankfurcie; dane osobowe zamieniam na znaczniki i przywracam po powrocie.")
            proposal = s.drafts.propose(case, message, identity.id, names).public()
            proposal["type"] = "proposal"
            proposal["docx"] = [d for d in s.vault.summaries({case}) if d["name"].lower().endswith(".docx")]
            return [text("Projekt gotowy. Przeczytaj go; zapiszę dopiero to, co zatwierdzisz."), proposal]
        count = len(s.documents(identity, case))
        s.narrate(identity, f"Rozumiem: pytanie o sprawę „{case}”. Czytam jej dokumenty ({count}).")
        s.narrate(identity, "Pytam asystenta we Frankfurcie" + ("; nazwiska i numery zamieniam na znaczniki." if s.pseudonymizes() else "."))
        answer = s.drafts.ask(case, message, identity.id, names)
        line = understood(answer["answer"])[1]
        if line:
            s.narrate(identity, "Jak to rozumiem: " + line)
        s.narrate(identity, "Sprawdzam, z których dokumentów pochodzi odpowiedź.")
        blocks = answer_blocks(answer["answer"])
        if answer["skipped"]:
            blocks.append(text("Nie czytałem (tylko TXT i DOCX): " + ", ".join(answer["skipped"]) + "."))
        return blocks

    # ------------------------------------------------------------ procedures taught by showing
    def _procedures(self, identity, message, plain, case, names, writable):
        s, admin = self.s, identity.scope == "admin"
        if identity.cases is not None and "procedury" not in identity.cases:
            return None        # a device limited to chosen cases does not see the office's procedures
        if plain.startswith(("nagraj", "naucz sie", "naucz", "pokaze ci", "pokaze jak")) or plain == "nowa procedura":
            if not admin:
                return [text("Procedury nagrywa się na komputerze kancelarii, w panelu stanowiska: tam widać ekran z programem.")]
            name = re.sub(r"^(nagraj procedur\w*|nagraj|naucz si[eę]|naucz|poka[zż][eę] ci jak|poka[zż][eę] ci|poka[zż][eę] jak|nowa procedura)\s*:?\s*",
                          "", message, flags=re.IGNORECASE).strip(" „”\"")
            name = re.sub(r"^(wypełniać|wypelniac|wypełnia[ćc] się|jak)\s+", "", name, flags=re.IGNORECASE)
            return [text("Pokaż mi to raz. Włącz nagrywanie, wypełnij formularz na fikcyjnej sprawie i mów na głos, "
                         "co wpisujesz w każde pole i dlaczego. Zrzuty ekranu trafią do modelu w UE tak, jak je widać, "
                         "dlatego nie nagrywaj prawdziwych danych."),
                    {"type": "record", "name": name[:80], "transcribes": s.transcribes()}]
        if plain in {"procedury", "lista procedur", "pokaz procedury", "czego sie nauczyles", "czego sie nauczyles?"}:
            known = s.procedures.names(identity.id)
            if not known:
                return [text("Nie znam jeszcze żadnej procedury." + (" Napisz „nagraj procedurę” i pokaż mi pierwszą."
                                                                    if admin else " Nagrywa się je w panelu stanowiska."))] + (
                    [buttons(("Nagraj procedurę", "nagraj procedurę"))] if admin else [])
            return [text("Znam te procedury. Wybierz, a przygotuję wartości dla otwartej sprawy:"),
                    buttons(*[(n, f"wypełnij {n}") for n in known[:20]])]
        found = re.fullmatch(r"(?:pokaz|opisz) procedure\s+(.+)", plain)
        if found:
            procedure = s.procedures.get(found.group(1), identity.id)
            lines = [f"{procedure.nazwa} ({procedure.program})" + (f": {procedure.cel}" if procedure.cel else "")]
            lines += [f"{n}. {k.pole}: {k.zrodlo}" + (f" (bo: {k.dlaczego})" if k.dlaczego else "")
                      for n, k in enumerate(procedure.kroki, 1)]
            return [text("\n".join(lines)), buttons(("Wypełnij dla tej sprawy", f"wypełnij {procedure.nazwa}"))]
        found = re.fullmatch(r"(?:wypelnij|uzupelnij|wpisz|wpisz ponownie)\s+(.+)", plain)
        if found:
            if case is None or case == "procedury":
                return [text("Dla której sprawy? Wybierz sprawę u góry i napisz jeszcze raz.")]
            if not s.may_see_case(identity, case):
                return [text("Nie ma takiej sprawy.")]
            again = plain.startswith("wpisz")
            cached = self._sheets.get((identity.id, case, norm(found.group(1))))
            sheet = cached if again and cached else s.procedures.fill(found.group(1), case, identity.id, names)
            self._sheets[(identity.id, case, norm(sheet["name"]))] = sheet
            if admin and sheet.get("rodzaj"):
                try:
                    return self._autofill(identity, sheet, case)
                except FillError as error:
                    # The form cannot be reached right now: the values are still useful to copy by hand.
                    return [text(str(error)), {"type": "fill", **sheet},
                            buttons(("Wpisz ponownie", f"wpisz ponownie {sheet['name']}"))]
            note = ("" if admin else " Wpisać to w formularz za Ciebie może komputer kancelarii: napisz to samo w panelu stanowiska.")
            return [text(f"Wartości do „{sheet['name']}” dla sprawy „{case}”. Przepisz albo skopiuj każdą do "
                         "właściwego pola; sprawdź je, zanim zatwierdzisz formularz." + note),
                    {"type": "fill", **sheet}]
        found = re.fullmatch(r"(?:otworz|wejdz na|przejdz na) (?:strone|adres)\s+(\S+)", plain)
        if found and admin:
            address = message.split()[-1]
            where = s.autofill.target("strona").open(address)
            return [text(f"Otworzyłem {where} w przeglądarce NotarAI. Jeśli strona prosi o logowanie, zaloguj się tam raz; "
                         "przeglądarka zapamięta to logowanie.")]
        return None

    def _autofill(self, identity, sheet, case) -> list[dict]:
        procedure = self.s.procedures.get(sheet["name"], identity.id)
        preview = self.s.autofill.fill(procedure, sheet["items"], actor=identity.id, case=case)
        filled = sum(1 for r in preview["report"] if r["state"] == "filled")
        problems = [r for r in preview["report"] if r["state"] in {"missing", "differs", "no-option", "refused", "empty"}]
        blocks = [text(f"Wpisałem {filled} " + ("pole" if filled == 1 else "pola" if 2 <= filled % 10 <= 4 and filled // 10 != 1 else "pól")
                       + f" w „{sheet['name']}”" + (f" ({preview['where']})" if preview["where"] else "") + ". "
                       + ("Sprawdź formularz na ekranie albo na zrzucie poniżej." if not problems else
                          "Część pól wymaga Twojej uwagi; są oznaczone poniżej.")),
                  {"type": "filled", **{k: preview[k] for k in ("procedure", "where", "report", "send", "send_missing")},
                   "image": base64.b64encode(preview["image"]).decode() if preview["image"] else None}]
        if any(r["state"] == "missing" for r in problems):
            blocks.append(text("Jeśli strona prosi o zalogowanie albo formularz jest na innej stronie, przejdź do niego "
                               "w oknie NotarAI i dotknij „Wpisz ponownie”."))
        actions = [("Wpisz ponownie", f"wpisz ponownie {sheet['name']}")]
        blocks.append(buttons(*actions))
        if preview["send"]:
            token, kind = preview["token"], preview["kind"]

            def send():
                result = self.s.autofill.send(token, identity.id, kind)
                image = base64.b64encode(result["image"]).decode() if result.get("image") else None
                done = (f"Wysłałem „{sheet['name']}”. Na ekranie jest teraz: {result['where']}. Sprawdź potwierdzenie."
                        if result["state"] == "sent" else
                        "Nacisnąłem przycisk wysyłania, ale nie widzę zmiany na ekranie. Sprawdź, czy wniosek został "
                        "przyjęty, zanim spróbujesz ponownie.")
                return [text(done)] + ([{"type": "image", "image": image, "alt": "Ekran po wysłaniu"}] if image else [])
            asked_to_send = bool(re.search(r"\b(wyslij|wysylaj|zloz|i wyslij|przeslij)\b", getattr(self, "_plain", "")))
            blocks.append(self._confirm(identity, f"Wysłać „{sheet['name']}” przyciskiem „{preview['send']}”? Wyślę dokładnie "
                                                  "to, co widać na zrzucie powyżej.", "Wyślij teraz", send,
                                        explicit=asked_to_send))
        elif preview["send_missing"]:
            blocks.append(text(f"Nie widzę przycisku „{preview['send_missing']}”, więc nie wyślę. Wyślij ręcznie."))
        return blocks

    # ------------------------------------------------------------ the notary's own workspace
    def _tiles(self, identity, message, plain):
        s, admin = self.s, identity.scope == "admin"
        key = "admin" if admin else identity.id
        if not re.search(r"kafel|narzedzi|pulpit|przypnij|odepnij", plain):
            return None
        layout = s.layouts.get(key)
        catalog = tools_for(admin)

        def stored(note):
            return [{"type": "layout", "layout": s.layouts.put(key, layout)}, text(note)]

        if re.fullmatch(r"(narzedzia|jakie (sa )?narzedzia\??|dodaj narzedzie|dodaj kafelek|pokaz narzedzia)", plain):
            have = {t["label"].lower() for t in layout["tiles"]}
            free = [t for t in catalog if t["label"].lower() not in have]
            return [text("Co chcesz mieć pod ręką? Dotknij, żeby dodać kafelek. Własny dodasz zdaniem "
                         "„dodaj kafelek Nazwa: polecenie”, np. „dodaj kafelek Pełnomocnictwo KW: przygotuj "
                         "pełnomocnictwo do złożenia wniosku wieczystoksięgowego”."),
                    buttons(*[("+ " + t["label"], "dodaj kafelek " + t["label"]) for t in free])]
        found = re.fullmatch(r"(?:dodaj kafelek|przypnij|dodaj narzedzie)\s+(.+)", message, re.IGNORECASE)
        if found and norm(message).startswith(("dodaj kafelek", "przypnij", "dodaj narzedzie")):
            wanted = found.group(1).strip()
            if ":" in wanted:
                label, say = (part.strip() for part in wanted.split(":", 1))
            else:
                tool = next((t for t in catalog if norm(t["label"]) == norm(wanted)), None)
                if tool is None:
                    return [text("Nie znam takiego narzędzia. Własny kafelek: „dodaj kafelek Nazwa: polecenie”."),
                            buttons(("Pokaż narzędzia", "narzędzia"))]
                label, say = tool["label"], tool["say"]
            if not label or not say:
                return [text("Podaj nazwę i polecenie: „dodaj kafelek Nazwa: polecenie”.")]
            layout["tiles"] = [t for t in layout["tiles"] if norm(t["label"]) != norm(label)] + [{"label": label, "say": say}]
            layout["show"] = True
            return stored(f"Dodałem kafelek „{label}”. Kafelki przestawisz przyciskiem „Ustaw” albo przeciągając.")
        found = re.fullmatch(r"(?:usun kafelek|odepnij|usun narzedzie)\s+(.+)", plain)
        if found:
            keep = [t for t in layout["tiles"] if norm(t["label"]) != found.group(1).strip()]
            if len(keep) == len(layout["tiles"]):
                return [text("Nie ma takiego kafelka.")]
            layout["tiles"] = keep
            return stored("Usunąłem kafelek.")
        if re.fullmatch(r"(ukryj|schowaj|wylacz) (kafelki|pulpit|narzedzia)", plain):
            layout["show"] = False
            return stored("Schowałem kafelki. Zostaje sama rozmowa; wrócą po „pokaż kafelki”.")
        if re.fullmatch(r"(pokaz|wlacz|kafelki|pulpit|moje kafelki)( kafelki| pulpit)?", plain):
            if not layout["tiles"]:
                return self._tiles(identity, "narzędzia", "narzedzia")
            layout["show"] = True
            return stored("Oto Twoje kafelki.")
        if re.fullmatch(r"(usun wszystkie kafelki|wyczysc pulpit|wyczysc kafelki)", plain):
            layout["tiles"], layout["show"] = [], False
            return stored("Pulpit jest pusty. Zostaje sama rozmowa.")
        return None

    def _help(self, admin: bool, writable: bool) -> list[dict]:
        lines = ["Piszesz zwykłym zdaniem. Na przykład:",
                 "• „dokumenty” albo „otwórz umowa”",
                 "• pytanie o sprawę: „kto jest sprzedającym?”",
                 "• „policz taksę od sprzedaży lokalu za 500 tys.”"]
        lines += ["• „narzędzia”, żeby ustawić sobie kafelki z tym, czego używasz najczęściej"]
        if writable:
            lines += ["• „przygotuj umowę sprzedaży lokalu” (nic nie zapiszę bez Twojej zgody)",
                      "• „notatka: klient przyniesie odpis w piątek” albo notatka głosowa: przycisk z mikrofonem",
                      "• „strony: Jan Kowalski, Anna Nowak”"]
        if admin:
            lines += ["• „gdzie są dane”: mowa na tym komputerze albo we Frankfurcie, kopia we Frankfurcie i jak długo",
                      "• „zrób kopię”, „kod odzyskiwania”",
                      "• „dodaj telefon” albo „dodaj telefon tylko do odczytu dla sprawy kowalski-2026”",
                      "• „urządzenia”, „cofnij telefon”",
                      "• „zasada: każdy akt musi zawierać „…””, „zasady”, „usuń zasadę 2”",
                      "• „naucz się stylu kancelarii” albo „naucz się stylu z D:\\Akty”, potem „styl kancelarii”",
                      "• „włącz nasłuch”, „dodaj mikrofon Sekretariat”, „nasłuch”, „notatki z rozmów”, „stenopisy”",
                      "• „kto czytał umowa.docx?”",
                      "• „otwórz umowa w Wordzie”, potem „zapisz do sejfu”",
                      "• „nagraj procedurę Wniosek o wpis w KW”, potem „wypełnij wniosek o wpis w KW”: wpiszę dane "
                      "w formularz sam, a wyślę dopiero, gdy zatwierdzisz",
                      "• „otwórz stronę https://…” w przeglądarce NotarAI (logujesz się w niej raz)",
                      "• „połącz pocztę”, „poczta”, „maile od Kowalskiego”, „dodaj mail 2 do sprawy”",
                      "• „zaloguj”, „wyłącz pseudonimizację”, „włącz dostęp spoza kancelarii”"]
        return [text("\n".join(lines))]

    def _documents(self, identity, case) -> list[dict]:
        items = self.s.documents(identity, case)
        if not items:
            return [text("Brak dokumentów" + (f" w sprawie „{case}”." if case else ".")
                         + " Dodaj plik spinaczem albo napisz „notatka: …”.")]
        head = f"Dokumenty sprawy „{case}”:" if case else "Wszystkie dokumenty:"
        return [text(head), {"type": "documents", "items": items[:60]}]

    def _find_document(self, identity, case, fragment: str):
        fragment = re.sub(r"\s+(w wordzie|do edycji|w edytorze)$", "", fragment).strip(" „”\"")
        items = self.s.documents(identity, case) or self.s.documents(identity, None)
        hits = [d for d in items if fragment in norm(d["name"])]
        exact = [d for d in hits if norm(d["name"]) == fragment or norm(d["name"]).rsplit(".", 1)[0] == fragment]
        if len(exact) == 1 or len(hits) == 1:
            return (exact or hits)[0]
        return hits[:20]

    def _fee(self, message, plain) -> list[dict]:
        catalog = self.s.fee_catalog()["rodzaje"]
        explicit = re.fullmatch(r"taksa (\S+) (\S+)", plain)
        kind = next((r for r in catalog if explicit and r["id"] == explicit.group(1)), None)
        amount = parse_amount(explicit.group(2) if kind else message)
        if kind is None:
            words = {w[:5] for w in re.findall(r"[a-z]{4,}", plain)} - {"taksa", "taksy", "takse", "polic", "kosztu"}
            scored = sorted(((len(words & {w[:5] for w in re.findall(r"[a-z]{4,}", norm(r["nazwa"]))}), r)
                             for r in catalog), key=lambda pair: -pair[0])
            if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                kind = scored[0][1]
            elif amount is not None:
                options = [r for score, r in scored[:6] if score > 0] or catalog[:6]
                return [text("Jakiej czynności dotyczy?"),
                        buttons(*[(r["nazwa"], f"taksa {r['id']} {amount}") for r in options])]
        if amount is None:
            return [text("Podaj wartość, np. „taksa od sprzedaży lokalu za 500 tys.”")]
        if kind is None:
            return [text("Jakiej czynności dotyczy?"),
                    buttons(*[(r["nazwa"], f"taksa {r['id']} {amount}") for r in catalog[:6]])]
        result = self.s.fee_estimate({"czynnosci": [{"rodzaj": kind["id"], "wartosc": float(amount)}]})
        return [text(result.get("tekst") or "\n".join(result.get("uwagi") or ["Nie udało się policzyć."])),
                text("Policzył to program według stawek maksymalnych, nie model.")]

    def _warnings(self, admin: bool) -> list[dict]:
        s, blocks = self.s, []
        status = s.status()
        if not status["enrolled"]:
            blocks.append(text("Uwaga: sejf nie ma kodu odzyskiwania. Po awarii komputera dokumentów nie da się odtworzyć."
                               + ("" if admin else " Utwórz go w panelu stanowiska na komputerze kancelarii.")))
            if admin:
                blocks.append(buttons(("Utwórz kod odzyskiwania", "kod odzyskiwania")))
        elif status["backup_overdue"]:
            blocks.append(text("Dawno nie było kopii zapasowej."
                               + ("" if admin else " Zrób ją w panelu stanowiska na komputerze kancelarii.")))
            if admin:
                blocks.append(buttons(("Zrób kopię teraz", "zrób kopię")))
        if admin and status["workcopies"]:
            blocks.append(text(f"Otwarte do edycji i niezapisane w sejfie: {status['workcopies']}."))
            blocks.append(buttons(("Pokaż otwarte", "otwarte")))
        return blocks

    # ------------------------------------------------------------ workstation intents
    def _listen(self, identity, message, plain):
        """Always-on microphones (workstation only)."""
        s = self.s
        if not re.search(r"nasluch|mikrofon|stenopis|notatki z rozmow|rozmowy z dzis|podsluch", plain):
            return None
        current = s.status_listen()
        if plain.startswith(("wlacz nasluch", "uruchom nasluch")):
            if not s.can_transcribe():
                return [text("Rozpoznawanie mowy nie jest jeszcze skonfigurowane (zaloguj stanowisko do NotarAI), "
                             "więc nasłuch nie miałby czego zapisać.")]

            def act():
                s.update_settings(lambda d: d["listen"].update(enabled=True, paused=False))
                return [text("Nasłuch włączony. Dodaj mikrofony zdaniem „dodaj mikrofon Sekretariat” albo "
                             "„dodaj mikrofon Gabinet”."), buttons(("Dodaj mikrofon", "dodaj mikrofon Sekretariat"))]
            return [self._confirm(identity,
                                  "Włączyć stały nasłuch? Mikrofony będą zapisywać rozmowy w kancelarii jako tekst: "
                                  "stenopisy odczytanych aktów trafią do spraw, a z rozmów i telefonów powstaną notatki. "
                                  "Dźwięku nie przechowuję. Klientów trzeba o tym poinformować (RODO, art. 13), np. "
                                  "tabliczką przy wejściu i zdaniem na początku rozmowy telefonicznej.",
                                  "Tak, włącz nasłuch", act)]
        if plain.startswith(("wylacz nasluch", "zakoncz nasluch")):
            s.update_settings(lambda d: d["listen"].update(enabled=False))
            filed = s.listening().flush()
            return [text("Nasłuch wyłączony." + (f" Zapisałem ostatnie rozmowy: {len(filed)}." if filed else ""))]
        if re.match(r"(wstrzymaj|pauza|zatrzymaj|przerwij) nasluch|pauza", plain):
            s.update_settings(lambda d: d["listen"].update(paused=True))
            return [text("Nasłuch wstrzymany. Mikrofony nic nie przesyłają, dopóki nie napiszesz „wznów nasłuch”.")]
        if plain.startswith(("wznow nasluch", "wznow")):
            s.update_settings(lambda d: d["listen"].update(paused=False))
            return [text("Nasłuch wznowiony.")]
        found = re.fullmatch(r"(?:dodaj|sparuj|podlacz) mikrofon\s*(.*)", plain)
        if found:
            name = message.split(None, 2)[2].strip(" „”\"") if len(message.split(None, 2)) > 2 else "Mikrofon"
            invitation = s.devices.invite(name[:80], "listen")
            blocks = [text(f"Mikrofon „{name}”. Na urządzeniu, które ma słuchać (tablet, telefon, komputer z mikrofonem), "
                           "otwórz Pocket tym kodem i zostaw je włączone na ładowarce. Kod działa raz, przez 5 minut. "
                           "Mikrofon nie ma dostępu do dokumentów.")]
            link = s.pairing_link(invitation["code"])
            if link:
                blocks.append({"type": "qr", "link": link})
            blocks.append({"type": "secret", "title": "Kod mikrofonu", "text": invitation["code"],
                           "hint": "Na tym komputerze: wklej w Pocket. Nie wysyłaj kodu e-mailem."})
            if not current["enabled"]:
                blocks.append(buttons(("Włącz nasłuch", "włącz nasłuch")))
            return blocks
        if "notatki z rozmow" in plain or "rozmowy z dzis" in plain or plain.startswith("stenopisy"):
            wanted = "stenopis-" if "stenopis" in plain else "rozmowa-"
            items = sorted((d for d in s.vault.summaries() if d["name"].startswith(wanted)), key=lambda d: -d["created"])[:12]
            if not items:
                return [text("Nie ma jeszcze " + ("stenopisów." if wanted == "stenopis-" else "notatek z rozmów."))]
            return [text(("Ostatnie stenopisy:" if wanted == "stenopis-" else "Ostatnie notatki z rozmów:")),
                    {"type": "documents", "items": [{"id": d["id"], "name": d["name"], "version": d["version"]} for d in items]}]
        listening = s.listening()
        mics = [d for d in s.devices.list() if d["scope"] == "listen" and not d["revoked"]]
        state = ("wyłączony" if not current["enabled"] else "wstrzymany" if current["paused"] else "włączony")
        lines = [f"Nasłuch: {state}."]
        for mic in mics:
            seen = listening.sources.get(mic["name"])
            lines.append(f"• {mic['name']}: " + (f"ostatni dźwięk {when(int(seen['last'] * 10**9))}" if seen else "jeszcze nic nie przesłał"))
        if not mics:
            lines.append("Nie ma jeszcze mikrofonów.")
        if listening.pending():
            lines.append(f"Do przepisania czeka fragmentów: {listening.pending()}.")
        actions = [("Dodaj mikrofon", "dodaj mikrofon Sekretariat"), ("Notatki z rozmów", "notatki z rozmów"),
                   ("Stenopisy", "stenopisy")]
        actions.insert(0, ("Włącz nasłuch", "włącz nasłuch") if not current["enabled"] else
                       ("Wznów nasłuch", "wznów nasłuch") if current["paused"] else ("Wstrzymaj nasłuch", "wstrzymaj nasłuch"))
        return [text("\n".join(lines)), buttons(*actions)]

    def _style(self, identity, message, plain):
        """Learning the office's way of writing from acts already on its computers (workstation only)."""
        s = self.s
        if not re.search(r"\bstyl\w*|\bnaucz sie (pisac|aktow|z aktow)|przeszukaj (komputer|dysk)", plain):
            return None
        if plain.startswith(("naucz", "przeszukaj", "skanuj", "ucz sie")):
            found = re.search(r"\b(?:z|w|ze)\s+((?:[A-Za-z]:\\|/)\S.*)$", message)
            roots = [found.group(1).strip().strip("„”\"")] if found else None
            if roots and not os.path.isdir(roots[0]):
                return [text("Nie ma takiego folderu na tym komputerze.")]
            from .style import default_roots

            chosen = roots or [str(r) for r in default_roots()]
            if not s.style.start(chosen, identity.id):
                return [text("Już się uczę. Napisz „stan nauki stylu”, żeby zobaczyć postęp.")]
            return [text("Zaczynam. Przeszukuję " + ", ".join(chosen) + " w poszukiwaniu aktów (DOCX, ODT, RTF, TXT). "
                         "Czytam je na miejscu: nic nie kopiuję i nic nie wysyłam. Zapamiętam tylko zdania, które "
                         "powtarzają się w wielu aktach, czyli styl kancelarii, a nie dane klientów. Może to potrwać "
                         "kilkanaście minut; napisz „stan nauki stylu”.")]
        progress = s.style.progress
        if progress.get("running"):
            return [text(f"Uczę się: przejrzałem {progress['files']} plików, znalazłem {progress['acts']} aktów.")]
        profile = s.style.profile()
        if profile is None:
            return [text("Nie znam jeszcze stylu kancelarii." + (" Napisz „naucz się stylu kancelarii” (cały komputer) "
                                                                  "albo „naucz się stylu z D:\\Akty”." if identity.scope == "admin" else ""))]
        counts = ", ".join(f"{kind}: {n}" for kind, n in sorted(profile["acts"].items(), key=lambda kv: -kv[1]))
        found_kind = next((k for k in profile["formulas"] if norm(k) in plain), None)
        if found_kind:
            lines = [f"• {f['text']}" for f in profile["formulas"][found_kind][:25]]
            return [text(f"Stałe sformułowania kancelarii ({found_kind}), w kolejności z aktów:\n" + "\n".join(lines))]
        kinds = [k for k, f in profile["formulas"].items() if f]
        return [text(f"Znam styl kancelarii z {sum(profile['acts'].values())} aktów ({counts}); przejrzałem "
                     f"{profile['files_scanned']} plików. Projekty piszę tymi sformułowaniami."
                     + ("" if profile.get("complete", True) else " Przeszukiwanie przerwałem po limicie czasu albo plików.")),
                buttons(*[(f"Styl: {k}", f"pokaż styl {k}") for k in kinds[:10]])]

    def _office_rules(self, identity, message, plain):
        """Everyone may read the rules; only the workstation may add or remove them."""
        from .rules import describe, parse

        s, admin = self.s, identity.scope == "admin"
        if plain in {"zasady", "zasady kancelarii", "pokaz zasady", "jakie sa zasady", "jakie sa zasady?"}:
            known = s.rules.all()
            if not known:
                return [text("Kancelaria nie ma jeszcze twardych zasad." + (
                    " Dodasz je zdaniem zaczynającym się od „zasada:”, np. „zasada: każdy akt musi zawierać "
                    "„Notariusz pouczył strony…””." if admin else ""))]
            lines = [f"{n}. {describe(rule)}" for n, rule in enumerate(known, 1)]
            blocks = [text("Zasady kancelarii (pilnuje ich program, nie model):\n" + "\n".join(lines))]
            if admin:
                blocks.append(buttons(*[(f"Usuń zasadę {n}", f"usuń zasadę {n}") for n in range(1, len(known) + 1)]))
            return blocks
        if plain.startswith(("zasada", "nowa zasada", "dodaj zasade")):
            if not admin:
                return [text("Zasady kancelarii ustawia się w panelu stanowiska.")]
            body = re.sub(r"^\s*(nowa zasada|dodaj zasadę|dodaj zasade|zasada)\s*:?\s*", "", message, flags=re.IGNORECASE)
            rule = parse(body)
            if rule is None:
                return [text("Tej zasady nie umiem sprawdzać kodem, więc jej nie dodam: musiałbym polegać na modelu. "
                             "Umiem pilnować, żeby dokument zawierał albo nigdy nie zawierał podanych słów w cudzysłowie, "
                             "żeby formularz nie poszedł bez wskazanego pola, godzin wysyłki w dni robocze oraz "
                             "stale włączonej pseudonimizacji.")]
            try:
                added = s.rules.add(rule, identity.id)
            except ValueError:
                return [text("Taka zasada już jest albo jest niepełna.")]
            return [text("Dodałem twardą zasadę: " + describe(added) + " Program sprawdzi ją przy każdym zapisie "
                         "i wysyłce; nie da się jej obejść poleceniem."), {"type": "rules"}]
        found = re.fullmatch(r"usun zasade (\d+)", plain)
        if found:
            if not admin:
                return [text("Zasady kancelarii zmienia się w panelu stanowiska.")]
            number = int(found.group(1))
            known = s.rules.all()
            if not 1 <= number <= len(known):
                return [text("Nie ma zasady o tym numerze.")]

            def act():
                removed = s.rules.remove(number, identity.id)
                return [text("Usunąłem zasadę: " + describe(removed)), {"type": "rules"}]
            return [self._confirm(identity, f"Usunąć zasadę {number}: {describe(known[number - 1])}", "Tak, usuń zasadę", act)]
        return None

    def _admin(self, identity, message, plain, case):
        s = self.s
        guide = self._guide(identity, message, plain)
        if guide is not None:
            return guide
        if plain in {"aktualizacja", "aktualizacje", "sprawdz aktualizacje", "sprawdz aktualizacje programu", "wersja",
                     "jaka wersja", "zaktualizuj", "aktualizuj"}:
            return self._update(identity, check=True)
        if plain in {"zainstaluj aktualizacje", "uruchom ponownie", "uruchom ponownie i zaktualizuj"}:
            return self._update(identity, check=False, install=True)
        where = self._where(identity, plain)
        if where is not None:
            return where
        on = plain.startswith(("wlacz", "uruchom", "zezwol"))
        off = plain.startswith(("wylacz", "zablokuj", "zatrzymaj"))
        if plain in {"stan", "status", "stan stanowiska", "jak stoimy", "jak stoimy?"}:
            return self._status()
        learned = self._style(identity, message, plain)
        if learned is not None:
            return learned
        heard = self._listen(identity, message, plain)
        if heard is not None:
            return heard
        mail = self._mail(identity, message, plain, case)      # before devices: "odłącz pocztę" is not a device
        if mail is not None:
            return mail
        if "kod odzyskiwania" in plain:
            if s.status()["enrolled"]:
                if plain.startswith("nowy"):
                    return [self._confirm(identity, "Wydać nowy kod odzyskiwania? Stary przestanie działać dla nowych kopii.",
                                          "Tak, wydaj nowy kod", lambda: self._recovery_code(True))]
                return [text("Kod odzyskiwania już istnieje i nie da się go wyświetlić ponownie. "
                             "Jeśli wydruk zaginął, napisz „nowy kod odzyskiwania”.")]
            return self._recovery_code(False)
        if re.search(r"\bkatalog kopii\b", plain):
            path = message.split(None, 2)[-1].strip() if len(message.split()) > 2 else ""
            if not path or norm(path) in {"kopii"}:
                return [text("Napisz „katalog kopii” i ścieżkę, np. „katalog kopii E:\\NotarAI-kopie”.")]
            s.update_settings(lambda d: d.update(backup_dir=path))
            return [text(f"Kopie będą trafiać do {path}. Zrobić pierwszą teraz?"), buttons(("Zrób kopię", "zrób kopię"))]
        if re.search(r"\bkopi[ae]\b", plain) and (on or off) and ("poza" in plain or "chmur" in plain):
            s.update_settings(lambda d: d["replica"].update(enabled=on))
            return [text("Kopia poza kancelarią włączona. Wysyłam zaszyfrowany plik raz na dobę." if on
                         else "Kopia poza kancelarią wyłączona.")]
        if re.search(r"\bkopi[aeę]\b", plain) and not plain.startswith(("gdzie", "kiedy")):
            return self._backup()
        if plain in {"urzadzenia", "telefony", "pokaz urzadzenia", "lista urzadzen"}:
            return self._devices(identity)
        if plain.startswith(("dodaj telefon", "dodaj urzadzenie", "dodaj tablet", "dodaj laptop", "sparuj", "nowy telefon")):
            return self._invite(message, plain)
        found = re.fullmatch(r"(?:cofnij|odlacz|usun|zablokuj)(?: dostep)?(?: urzadzenia| urzadzenie)?\s+(.+)", plain)
        if found:
            return self._revoke(identity, found.group(1))
        if plain.startswith(("dziennik", "kto czytal", "kto otwieral", "historia", "kto zmienial")):
            return self._audit(identity, case, plain)
        if plain.startswith(("zuzycie", "ile kosztowalo", "ile zuzylismy", "koszty ai")):
            usage = s.usage()
            if not usage:
                return [text("Asystent nie był jeszcze używany.")]
            return [text("\n".join(
                f"{row['calls']} wywołań ({ {'draft': 'projekty', 'chat': 'pytania', 'smoke': 'testy'}.get(row['purpose'], row['purpose']) }): "
                f"{row['input_tokens']} tokenów wejścia, {row['output_tokens']} wyjścia." for row in usage))]
        if (on or off) and re.search(r"pseudonim|maskowani|znacznik", plain):
            s.update_settings(lambda d: d["ai"].update(pseudonymize=on))
            return [text("Pseudonimizacja włączona: PESEL, NIP, numery KW, rachunki i wskazane osoby model zobaczy jako znaczniki."
                         if on else "Pseudonimizacja wyłączona: tekst dokumentów trafia do modelu w UE bez zmian. "
                                    "Nadal nic nie jest tam zapisywane.")]
        if (on or off) and re.search(r"spoza kancelarii|zdaln|poza kancelari|tunel", plain):
            try:
                s.update_settings(lambda d: d["tunnel"].update(enabled=on))
            except ValueError:
                return [text("Brakuje adresu przekaźnika albo strony Pocket. Otrzymasz je przy wdrożeniu.")]
            return [text("Dostęp spoza kancelarii włączony. Nowe telefony sparujesz kodem QR: napisz „dodaj telefon”."
                         if on else "Dostęp spoza kancelarii wyłączony. Telefony działają tylko na tym komputerze.")]
        if (on or off) and re.search(r"asystent|\bai\b|sztuczn", plain):
            if not s.account_configured():
                return [text("To stanowisko nie ma jeszcze danych konta NotarAI. Otrzymasz je przy wdrożeniu.")]
            if off:
                s.logout()
                return [text("Wylogowałem stanowisko z NotarAI. Czat działa dalej dla dokumentów, taksy i poleceń; "
                             "na pytania odpowiem znowu po zalogowaniu.")]
            if s.signed_in():
                return [text("Asystent działa: po prostu pisz w tym czacie.")]
            return [text("Zaloguj się kontem NotarAI, a odpowiem na pytania w tym czacie:"), {"type": "login"}]
        if plain in {"zaloguj", "zaloguj sie", "logowanie", "zaloguj do ai"}:
            if not s.account_configured():
                return [text("To stanowisko nie ma jeszcze danych konta NotarAI.")]
            return [{"type": "login"}]
        if plain in {"wyloguj", "wyloguj sie", "wyloguj z ai"}:
            s.logout()
            return [text("Wylogowano z AI.")]
        if plain in {"programy", "polaczone programy", "jakie programy", "polacz program", "polacz programy"}:
            return self._programs()
        if plain in {"otwarte", "co jest otwarte", "co jest otwarte?", "pokaz otwarte", "kopie robocze"}:
            return self._workcopies()
        found = re.fullmatch(r"(?:otworz|edytuj)\s+(.+?)\s+(?:w wordzie|do edycji|w edytorze)", plain) \
            or re.fullmatch(r"edytuj\s+(.+)", plain)
        if found:
            match = self._find_document(identity, case, found.group(1))
            if not isinstance(match, dict):
                return [text("Który dokument otworzyć do edycji?")] + (
                    [buttons(*[(d["name"], f"edytuj {d['name']}") for d in match[:10]])] if match else [])
            s.workcopies.checkout(match["id"], identity.id)
            return [text(f"Otworzyłem {match['name']} w edytorze. Gdy zapiszesz i zamkniesz, napisz „zapisz do sejfu”."),
                    buttons(("Zapisz do sejfu", f"zapisz do sejfu {match['name']}"))]
        found = re.fullmatch(r"zapisz do sejfu\s*(.*)", plain)
        if found:
            return self._checkin(identity, found.group(1))
        found = re.fullmatch(r"porzuc(?: zmiany)?(?: w)?\s+(.+)", plain)
        if found:
            copy = self._one_copy(found.group(1))
            if copy is None:
                return [text("Nie znalazłem takiej kopii roboczej.")]
            return [self._confirm(identity, f"Porzucić zmiany w „{copy['name']}”? Nie da się ich odzyskać.",
                                  "Tak, porzuć zmiany", lambda: self._discard(identity, copy))]
        return None

    # ------------------------------------------------------------ mail (this computer's own program)
    # ------------------------------------------------------------ program updates (workstation only)
    def _update(self, identity, *, check: bool, install: bool = False) -> list[dict]:
        program = self.s.program
        current = program.current
        if current is None:
            return [text("Ta kopia programu nie pochodzi z instalatora, więc nie aktualizuje się sama.")]
        state = program.check() if check else dict(program.state)
        head = f"Zainstalowana wersja: {current['version']}."
        if state.get("full_installer"):
            return [text(head + f" Jest wersja {state['available']} z nowymi bibliotekami: tym razem trzeba pobrać pełny "
                         "instalator ze strony pobierania (sejf i ustawienia zostają).")]
        ready = program.ready_version()
        if ready:
            def restart():
                self.s.restart_for_update()
                return [text(f"Instaluję wersję {ready}. Za chwilę otworzy się nowe okno NotarAI; to możesz zamknąć.")]
            if install:
                return [self._confirm(identity, f"Uruchomić NotarAI ponownie i zainstalować wersję {ready}? Potrwa to kilka sekund.",
                                      "Tak, zaktualizuj", restart)]
            return [text(head + f" Pobrałem aktualizację {ready} (kilkaset kilobajtów, suma kontrolna sprawdzona). "
                         "Zainstaluje się przy następnym uruchomieniu albo teraz:"),
                    buttons(("Uruchom ponownie i zaktualizuj", "zainstaluj aktualizację"))]
        if state.get("error"):
            return [text(head + " " + state["error"])]
        return [text(head + " To najnowsza wersja.")]

    # ------------------------------------------------------------ first-run guide (workstation only)
    def _guide_card(self, step) -> list[dict]:
        extra = [] if step.get("required") else [("Pomiń ten krok", "pomiń krok")]
        return [text(f"Przewodnik · krok {step['number']} z {step['of']}: {step['title']}\n{step['why']}"),
                buttons(*step["actions"], *extra, ("Cała lista", "przewodnik"))]

    def _guide(self, identity, message, plain):
        s = self.s
        guide = s.onboarding
        if plain in {"przewodnik", "pierwsze kroki", "przewodnik pierwszego uruchomienia", "konfiguracja", "onboarding",
                     "jak zaczac", "od czego zaczac"}:
            marks = {True: "✓", False: "○"}
            lines = [f"{marks[st['done']]} {i}. {st['title']}" + (" (pominięty)" if st["skipped"] and not st["done"] else "")
                     for i, st in enumerate(guide.status(), 1)]
            step = guide.current()
            blocks = [text("Przewodnik pierwszego uruchomienia:\n" + "\n".join(lines))]
            if step is None:
                missing = [st for st in guide.status() if not st["done"]]
                return blocks + ([text("Pominięte kroki możesz zrobić teraz:"),
                                  buttons(("Wróć do pominiętych", "przewodnik od nowa"))] if missing else
                                 [text("Wszystko gotowe.")])
            return blocks + self._guide_card(step)
        if plain in {"pomin krok", "pomin", "pomin ten krok", "pozniej"}:
            step = guide.current()
            if step is None:
                return [text("Przewodnik jest skończony. Napisz „przewodnik”, żeby zobaczyć listę.")]
            if not guide.skip(step["key"]):
                return [text(f"Tego kroku nie da się pominąć: {step['title']}. {step['why']}"),
                        buttons(*step["actions"])]
            following = guide.current()
            return ([text(f"Pominąłem: {step['title']}. Wrócisz do tego, pisząc „przewodnik”.")]
                    + (self._guide_card(following) if following else [text("To był ostatni krok.")]))
        if plain in {"przewodnik od nowa", "wroc do pominietych"}:
            guide.restart()
            step = guide.current()
            return self._guide_card(step) if step else [text("Wszystkie kroki są już zrobione.")]
        if plain in {"rozpoznaj komputer", "co jest na komputerze", "co znalazles", "sprawdz komputer",
                     "rozpoznanie", "co jest na tym komputerze"}:
            return self._environment(refresh=plain != "co znalazles")
        # folders chosen in a Windows dialog on this computer
        if plain in {"wybierz folder aktow", "wskaz folder aktow"}:
            return [{"type": "pick-folder", "purpose": "akty", "label": "Wybierz folder z aktami…"},
                    text("Albo napisz ścieżkę, np. „folder aktów D:\\Akty”.")]
        if plain in {"wybierz folder kopii", "wskaz folder kopii", "wybierz dysk na kopie"}:
            return [{"type": "pick-folder", "purpose": "kopie", "label": "Wybierz folder na kopie…"},
                    text("Najlepiej inny dysk niż ten komputer (pendrive, dysk zewnętrzny, dysk sieciowy). "
                         "Albo napisz „katalog kopii E:\\NotarAI-kopie”.")]
        found = re.fullmatch(r"(?:folder aktow|katalog aktow|akty sa w|akty trzymamy w)\s+(.+)", plain)
        if found:
            path = message.split(None, 2)[-1].strip().strip("„”\"") if len(message.split()) > 2 else ""
            if not path or not os.path.isdir(path):
                return [text("Nie ma takiego folderu na tym komputerze.")]
            s.update_settings(lambda d: d.update(acts_dir=path))
            return [text(f"Folder aktów: {path}. Nauczyć się stylu kancelarii z aktów w tym folderze?"),
                    buttons(("Tak, ucz się", f"naucz się stylu z {path}"))]
        if plain in {"naucz sie stylu z folderu aktow", "ucz sie z folderu aktow"}:
            folder = s.settings().acts_dir
            if not folder:
                return [text("Najpierw wskaż folder z aktami."), {"type": "pick-folder", "purpose": "akty",
                                                                   "label": "Wybierz folder z aktami…"}]
            return self._style(identity, f"naucz się stylu z {folder}", norm(f"naucz się stylu z {folder}"))
        # activities: shown once, then done by the program
        if plain in {"czynnosci", "czynnosci kancelarii", "moje czynnosci", "automaty"}:
            return self._activities(identity)
        found = re.fullmatch(r"(?:dodaj czynnosc|nowa czynnosc|robimy)\s+(.+)", plain)
        if found:
            guide.choose(message.split(None, 2)[-1] if plain.startswith(("dodaj", "nowa")) else message.split(None, 1)[-1])
            return self._activities(identity)
        found = re.fullmatch(r"(?:usun czynnosc|nie robimy)\s+(.+)", plain)
        if found:
            guide.drop(message.split(None, 2)[-1] if plain.startswith("usun") else message.split(None, 2)[-1])
            return self._activities(identity)
        if plain in {"rodzaje aktow", "jakie akty"}:
            from .onboarding import ACT_KINDS

            return [text("Wybierz rodzaj aktu do próby. Najpierw dodaj do sprawy pliki (np. odpis KW, dowody stron "
                         "na fikcyjnych danych), potem poproś o projekt. Każdy zatwierdzony akt uczy program Waszego stylu."),
                    buttons(*[(kind, f"przygotuj projekt: {kind.lower()}") for kind in ACT_KINDS])]
        return None

    def _environment(self, refresh: bool) -> list[dict]:
        found = self.s.environment(refresh=refresh)
        settings = self.s.settings()
        lines, actions = ["Co znalazłem na tym komputerze:"], []
        if found["mail"]:
            names = ", ".join(m["label"] for m in found["mail"])
            connected = settings.mail.source is not None
            lines.append(f"• Poczta: {names}" + (" (podłączona)" if connected else ""))
            if not connected:
                actions += [(f"Podłącz {m['label']}", f"połącz pocztę {m['kind']}") for m in found["mail"]]
        else:
            lines.append("• Poczta: nie znalazłem Thunderbirda ani klasycznego Outlooka (nowy Outlook: przez folder z wiadomościami)")
        groups = {"kancelaryjny": "Programy kancelaryjne", "podpis": "Podpis kwalifikowany", "urzędowy": "Programy urzędowe",
                  "edytor": "Edytor tekstu", "przegladarka": "Przeglądarki"}
        for kind, title in groups.items():
            items = [p for p in found["programs"] if p["kind"] == kind]
            if items:
                lines.append(f"• {title}: " + "; ".join(f"{p['shown']} ({p['use']})" for p in items))
                if kind == "kancelaryjny":
                    actions += [(f"Podłącz {p['shown']}", f"dodaj czynność Wpis do programu {p['shown']}") for p in items]
        if not any(p["kind"] == "kancelaryjny" for p in found["programs"]):
            lines.append("• Programy kancelaryjne: żadnego nie rozpoznałem po nazwie. Każdy program Windows podłączysz, "
                         "pokazując raz czynność: „nagraj procedurę” i nazwa.")
        if found["acts"]:
            lines.append("• Foldery z aktami: " + "; ".join(f"{a['path']} ({a['acts']} plików)" for a in found["acts"][:3]))
            if settings.acts_dir is None:
                top = found["acts"][0]["path"]
                actions.append(("Akty są tutaj: " + top[-40:], f"folder aktów {top}"))
        else:
            lines.append("• Folderów z aktami nie znalazłem w Dokumentach, na pulpicie ani na dyskach D: do H:.")
        lines.append("Nic nie zostało zmienione ani wysłane; to tylko przegląd.")
        blocks = [text("\n".join(lines))]
        if actions:
            blocks.append(buttons(*actions[:10]))
        return blocks

    def _activities(self, identity) -> list[dict]:
        from .onboarding import ACTIVITIES
        from .procedures import slug as procedure_slug

        guide = self.s.onboarding
        chosen = guide.activities()
        learned = {p["slug"] for p in self.s.procedures.list()}
        lines, actions = [], []
        for name in chosen:
            done = procedure_slug(name) in learned
            lines.append(("✓ " if done else "○ ") + name + (" — program robi to sam" if done else " — do pokazania raz"))
            actions.append((f"Zrób: {name}", f"wypełnij {name}") if done else (f"Pokaż raz: {name}", f"nagraj procedurę {name}"))
        suggested = [a for a in ACTIVITIES if a not in chosen]
        blocks = [text(("Czynności kancelarii:\n" + "\n".join(lines)) if lines else
                       "Wybierz czynności, które robicie. Pierwszy raz zrobisz każdą sam, a program nagra ekran i Twój "
                       "komentarz; od drugiego razu wypełni ją sam, a wyśle dopiero po Twoim zatwierdzeniu.")]
        if actions:
            blocks.append(buttons(*actions[:12]))
        if suggested:
            blocks.append(text("Dodaj czynność (albo napisz „dodaj czynność” i nazwę):"))
            blocks.append(buttons(*[(f"+ {a}", f"dodaj czynność {a}") for a in suggested]))
        return blocks

    # ------------------------------------------------------------ several workstations: names, messenger, printers
    def who(self, identity) -> str:
        """Where a command comes from: this station's name, or the paired device's name."""
        if identity.scope == "admin":
            return self.s.station_name()
        found = self.s.devices.lookup(identity.id)
        return (found or {}).get("name") or "urządzenie"

    def _office(self, identity, message, plain, case):
        s = self.s
        link = s.office
        admin = identity.scope == "admin"
        found = re.fullmatch(r"(?:nazwij (?:to )?stanowisko|to stanowisko to|nazwa stanowiska)\s*:?\s+(.+)", plain)
        if found:
            if not admin:
                return [text("Nazwę stanowiska ustawia się na tym komputerze.")]
            name = " ".join(message.split()[len(message.split()) - len(found.group(1).split()):])[:60].strip(" „”\"")
            s.update_settings(lambda d: d.update(station_name=name))
            return [text(f"To stanowisko nazywa się teraz „{name}”. Tak będzie podpisane wszystko, co stąd wyjdzie: "
                         "polecenia, wiadomości, terminy i wpisy w dzienniku.")]
        if plain in {"polacz drugie stanowisko", "dodaj stanowisko", "polacz stanowiska", "polacz komputery",
                     "dodaj komputer", "drugie stanowisko"}:
            if not admin:
                return [text("Stanowiska łączy się na komputerze kancelarii.")]
            if not s.settings().station_name:
                return [text("Najpierw nazwij to stanowisko, np. „nazwij stanowisko Gabinet”.")]
            code = link.invite()
            s.start_office_server()
            return [{"type": "code", "title": "Na drugim komputerze otwórz NotarAI i napisz:",
                     "text": f"dołącz do kancelarii {code}", "hint": "Kod jest ważny 10 minut i działa raz."},
                    text("Po połączeniu sprawy, dokumenty, kalendarz, komunikator i lekcje będą wspólne. Każdy "
                         "komputer zachowuje swój zaszyfrowany sejf, a w sieci wszystko idzie zaszyfrowane kluczem kancelarii. "
                         "Jeśli Windows zapyta o zaporę, zezwól na sieć prywatną.")]
        found = re.fullmatch(r"dolacz do kancelarii\s+(\S+:\d+\s+\S+)", plain)
        if found:
            if not admin:
                return [text("Do kancelarii dołącza się na komputerze, nie na telefonie.")]
            if not s.settings().station_name:
                return [text("Najpierw nazwij to stanowisko, np. „nazwij stanowisko Sekretariat”.")]
            other = link.join(message.split(None, 3)[-1])
            s.start_office_server()
            return [text(f"Połączyłem stanowisko „{s.station_name()}” ze stanowiskiem „{other}”. Za kilka sekund "
                         "zobaczysz wspólne sprawy, kalendarz i wiadomości.")]
        if plain in {"stanowiska", "komputery", "polaczone stanowiska", "kto jest w kancelarii"}:
            peers = link.peers()
            lines = [f"To stanowisko: {s.station_name()}."]
            for peer in peers:
                seen = link.stations.get(peer["name"], {})
                state_ = (f"ostatni kontakt {when(int(seen['seen'] * 10**9))}" if seen.get("seen") else "jeszcze bez kontaktu")
                lines.append(f"• {peer['name']} ({peer['address']}): {state_}"
                             + (f"; drukarki: {', '.join(seen['printers'])}" if seen.get("printers") else "")
                             + ("; podgląd ekranu dozwolony" if seen.get("screen") else ""))
            devices = [d for d in s.devices.list() if not d["revoked"]]
            if devices:
                lines.append("Urządzenia: " + ", ".join(f"{d['name']} ({ {'write': 'zapis', 'read': 'odczyt', 'listen': 'mikrofon'}.get(d['scope'], d['scope'])})" for d in devices))
            if not peers:
                lines.append("Nie ma jeszcze innych stanowisk. Napisz „połącz drugie stanowisko”.")
            return [text("\n".join(lines))]
        found = re.fullmatch(r"odlacz stanowisko\s+(.+)", plain)
        if found and admin:
            name = message.split(None, 2)[-1]
            return [text(f"Odłączyłem stanowisko „{name}”." if link.forget(name) else "Nie ma takiego stanowiska.")]
        # --- messenger
        found = re.fullmatch(r"(?:napisz do|wiadomosc do|przekaz do)\s+([^:]+?)\s*:\s*(.+)", plain, re.S)
        if found and identity.scope in {"admin", "write"}:
            raw = re.fullmatch(r"(?is)\S+\s+\S+\s+([^:]+?)\s*:\s*(.+)", message)
            to, body = (raw.group(1).strip(), raw.group(2).strip()) if raw else (found.group(1), found.group(2))
            entry = {"from": self.who(identity), "to": to, "text": body[:4000], "created": time.time_ns()}
            s.vault.message_put(secrets.token_hex(8), entry)
            blocks = [text(f"Wysłałem do „{to}”: {body}")]
            return blocks + self._date_in(body, case)
        if plain in {"wiadomosci", "komunikator", "czat kancelarii", "co pisali", "nowe wiadomosci"}:
            self._read_messages[identity.id] = time.time_ns()
            messages = s.vault.messages(20)
            if not messages:
                return [text("Nie ma jeszcze wiadomości. Napisz np. „napisz do Sekretariat: klient Kowalski będzie o 12”.")]
            lines = [f"{when(m['created'])} {m['from']} → {m['to']}: {m['text']}" for m in messages[-15:]]
            last = messages[-1]
            return [text("\n".join(lines))] + self._date_in(last["text"], case)
        # --- printers and scanners: installed on each station and found in the office network
        if plain in {"drukarki", "jakie drukarki", "pokaz drukarki", "skanery", "drukarki i skanery",
                     "znajdz drukarki", "szukaj drukarek", "znajdz skanery", "odswiez drukarki", "urzadzenia sieciowe"}:
            refresh = plain.startswith(("znajdz", "szukaj", "odswiez"))
            if refresh:
                s.narrate(identity, "Szukam drukarek i skanerów w sieci kancelarii (Bonjour/mDNS, ok. 3 sekundy).")
            network = s.find_devices(refresh=refresh)
            names = s.device_names()
            lines = ["Drukarki zainstalowane w Windows:", f"• {s.station_name()}: " + (", ".join(s.office_printers()) or "brak")]
            for name, seen in link.stations.items():
                lines.append(f"• {name}: " + (", ".join(seen.get("printers") or []) or "brak"))
            for kind, title in (("drukarka", "Drukarki w sieci"), ("skaner", "Skanery w sieci")):
                items = [d for d in network if d["kind"] == kind]
                lines.append(f"{title}:" if items else f"{title}: nie znalazłem.")
                for d in items:
                    own = names.get(d["id"])
                    drive = {"ipp": "druk bez sterownika", "ipps": "druk bez sterownika", "escl": "skan bez sterownika",
                             "escls": "skan bez sterownika"}.get(d["protocol"], "wymaga sterownika")
                    lines.append(f"• {('„' + own + '” – ') if own else ''}{d['model']} ({d['address']}, {drive})")
            unnamed = [d for d in network if not names.get(d["id"])]
            blocks = [text("\n".join(lines))]
            if unnamed:
                blocks.append(text("Nazwij urządzenie, żeby wydawać mu polecenia, np. „nazwij drukarkę "
                                   f"{unnamed[0]['model']} jako Sekretariat”."))
            blocks.append(buttons(("Szukaj ponownie", "znajdź drukarki")))
            return blocks
        found = re.fullmatch(r"nazwij (drukarke|skaner|urzadzenie)\s+(.+?)\s+jako\s+(.+)", plain)
        if found:
            if not admin:
                return [text("Nazwy urządzeń nadaje się na komputerze kancelarii.")]
            from .peripherals import match as find_device
            device = find_device(s.find_devices(), s.device_names(), found.group(2))
            if device is None:
                return [text("Nie widzę takiego urządzenia. Napisz „znajdź drukarki”, żeby poszukać.")]
            name = message[len(message) - len(found.group(3)):].strip(" „”\"")[:40]
            s.update_settings(lambda d: d["device_names"].update({device["id"]: name}))
            return [text(f"{'Drukarka' if device['kind'] == 'drukarka' else 'Skaner'} {device['model']} nazywa się teraz "
                         f"„{name}”. Ta nazwa działa na wszystkich stanowiskach, np. „wydrukuj umowa na drukarce {name}”.")]
        found = re.fullmatch(r"(?:wydrukuj|drukuj)\s+(.+?)(?:\s+(?:na drukarce|drukarka)\s+(.+?))?(?:\s+(?:w|na stanowisku|na)\s+(\S+))?", plain)
        if found and identity.scope in {"admin", "write"}:
            match = self._find_document(identity, case, found.group(1))
            if not isinstance(match, dict):
                return [text("Który dokument wydrukować?")] + ([{"type": "documents", "items": match}] if match else [])
            _, name, data = s.vault.get(match["id"], actor=identity.id)
            printer = found.group(2)
            station = found.group(3)
            if printer:
                from .peripherals import match as find_device
                device = find_device([d for d in s.find_devices() if d["kind"] == "drukarka"], s.device_names(), printer)
                if device is not None:
                    s.narrate(identity, f"Drukuję {name} na drukarce sieciowej {device['model']} ({device['address']}); "
                                        "dokument Worda najpierw zamieniam na PDF.")
                    s.print_network(device, name, data)
                    return [text(f"Wysłałem {name} na drukarkę „{s.device_names().get(device['id'], device['model'])}”.")]
            peer = next((p["name"] for p in link.peers() if station and norm(p["name"]) == station), None)
            if peer:
                ident = link.request(peer, "print", name=name, data=base64.b64encode(data).decode(), printer=printer)
                job = s.start_job(identity, lambda: self._wait_answer(ident, f"Drukuję {name} na stanowisku {peer}."))
                return [text(f"Wysłałem {name} do druku na stanowisku „{peer}”."), {"type": "job", "id": job}]
            if identity.scope != "admin":
                return [text("Napisz, na której drukarce albo stanowisku wydrukować, np. „wydrukuj umowa na drukarce Sekretariat”.")]
            s.office_print(name, data, printer)
            return [text(f"Drukuję {name}" + (f" na drukarce {printer}." if printer else " na domyślnej drukarce."))]
        found = re.fullmatch(r"(?:zeskanuj|skanuj|zrob skan)(?: do sprawy)?(?:\s+(?:na skanerze|skaner|ze skanera)\s+(.+?))?(\s+w kolorze|\s+kolor)?(\s+z podajnika|\s+podajnik)?", plain)
        if found and identity.scope in {"admin", "write"}:
            if case is None or not s.may_see_case(identity, case):
                return [text("Do której sprawy? Wybierz sprawę u góry: skan zapiszę w jej dokumentach.")]
            from .peripherals import match as find_device
            scanners = [d for d in s.find_devices() if d["kind"] == "skaner"]
            device = find_device(scanners, s.device_names(), found.group(1)) if found.group(1) else (scanners[0] if len(scanners) == 1 else None)
            if device is None:
                if not scanners:
                    return [text("Nie widzę skanera w sieci. Napisz „znajdź skanery”; skaner musi obsługiwać skanowanie "
                                 "przez sieć (eSCL/AirScan), co ma większość urządzeń wielofunkcyjnych.")]
                names = s.device_names()
                return [text("Na którym skanerze?"), buttons(*[(names.get(d["id"], d["model"]), f"zeskanuj na skanerze {names.get(d['id'], d['model'])}") for d in scanners])]
            color, feeder = bool(found.group(2)), bool(found.group(3))

            def scan():
                s.narrate(identity, f"Skanuję na {device['model']} ({'kolor' if color else 'skala szarości'}, "
                                    f"{'podajnik' if feeder else 'szyba'}), 300 dpi, do PDF.")
                pdf = s.scan(device, color=color, feeder=feeder)
                name = f"skan {time.strftime('%Y-%m-%d %H-%M')}.pdf"
                doc_id, version = s.vault.put(None, 0, name, pdf, actor=identity.id, case=case)
                return [text(f"Zeskanowałem do sprawy „{case}” jako {name}."),
                        {"type": "documents", "items": [{"id": doc_id, "name": name, "version": version}]}]
            job = s.start_job(identity, scan)
            return [text(f"Skanuję na „{s.device_names().get(device['id'], device['model'])}”…"), {"type": "job", "id": job}]
        # --- screen of another station
        found = re.fullmatch(r"(?:pokaz|podglad|zobacz) ekran(?:u)?\s+(.+)", plain)
        if found and admin:
            station = next((p["name"] for p in link.peers() if norm(p["name"]) in found.group(1)), None)
            if station is None:
                return [text("Którego stanowiska? Napisz „stanowiska”, żeby zobaczyć listę.")]
            ident = link.request(station, "screen")
            job = s.start_job(identity, lambda: self._wait_answer(ident, f"Ekran stanowiska {station}"))
            return [text(f"Proszę stanowisko „{station}” o obraz ekranu…"), {"type": "job", "id": job}]
        if plain in {"zezwol na podglad ekranu", "wlacz podglad ekranu", "zabron podgladu ekranu", "wylacz podglad ekranu"}:
            if not admin:
                return [text("To ustawia się na komputerze, którego ekran ma być widoczny.")]
            allow = plain.startswith(("zezwol", "wlacz"))
            s.update_settings(lambda d: d.update(allow_screen=allow))
            return [text("Inne stanowiska kancelarii mogą teraz zobaczyć ekran tego komputera (każde spojrzenie "
                         "pokażę tutaj)." if allow else "Podgląd ekranu tego komputera jest wyłączony.")]
        # --- microphones of the whole office
        if plain in {"mikrofony", "co slychac", "podglad mikrofonow", "co wychwycily mikrofony"}:
            notes = sorted((d for d in s.vault.summaries() if d["name"].startswith(("rozmowa-", "stenopis-"))),
                           key=lambda d: -d["created"])[:8]
            mics = [d for d in s.devices.list() if d["scope"] == "listen" and not d["revoked"]]
            lines = ["Mikrofony tego stanowiska: " + (", ".join(m["name"] for m in mics) if mics else "brak") + "."]
            if notes:
                lines.append("Ostatnio wychwycone (ze wszystkich stanowisk):")
                lines += [f"• {when(d['created'])}: {d['name'].rsplit('-', 1)[-1].removesuffix('.txt')} – {d['name']}" for d in notes]
            else:
                lines.append("Mikrofony nic jeszcze nie wychwyciły.")
            return [text("\n".join(lines))] + ([{"type": "documents", "items": [
                {"id": d["id"], "name": d["name"], "version": d["version"]} for d in notes]}] if notes else [])
        return None

    def _wait_answer(self, ident: str, title: str) -> list[dict]:
        """Wait (in a background job) for the other station's answer to a request."""
        for _ in range(90):
            answer = self.s.office.answers.pop(ident, None)
            if answer is not None:
                if answer.get("image"):
                    return [text(title + ":"), {"type": "image", "image": answer["image"], "alt": title}]
                return [text(answer.get("detail") or ("Gotowe." if answer.get("ok") else "Nie udało się."))]
            time.sleep(1)
        return [text("Drugie stanowisko nie odpowiedziało. Sprawdź, czy NotarAI jest tam włączony.")]

    def _date_in(self, body: str, case) -> list[dict]:
        """A date in a message becomes a proposed calendar entry (the notary decides)."""
        from .terminarz import label, parse_when

        parsed = parse_when(body, self.s.calendar.now())
        if parsed is None:
            return []
        start, what = parsed
        when_text = start.strftime("%d.%m.%Y %H:%M")
        return [text(f"W wiadomości jest termin: {label(start, self.s.calendar.now())} – {what[:80]}. Dodać do kalendarza?"),
                buttons(("Dodaj do kalendarza", f"termin {when_text} {what[:120]}"))]

    # ------------------------------------------------------------ thinking ahead: what to do now
    def suggestions(self, identity, case) -> list[dict]:
        """Two or three next steps from what the program sees: appointments, mail, the chosen case,
        lessons to confirm, copies. Each is a sentence the program understands, with the reason."""
        from .registers import land_register_numbers, pesels_in

        s, found = self.s, []
        writable = identity.scope in {"admin", "write"}
        if identity.scope == "listen":
            return []
        try:
            soon = s.calendar.upcoming(2, cases=identity.cases)
        except Exception:
            soon = []
        for entry in soon[:4]:
            if entry.get("case") and entry.get("case") != case:
                found.append({"label": f"{entry['label']}: {entry['title'][:40]}", "say": f"sprawa {entry['case']}",
                              "why": "termin w kalendarzu: otwórz sprawę i sprawdź, czy wszystko gotowe"})
        if case is not None and writable and s.may_see_case(identity, case):
            names = [d["name"] for d in s.documents(identity, case)]
            body = s.drafts.case_text(case, identity.id) if names else ""
            checked = " ".join(names)
            for number in land_register_numbers(body):
                if "KW " + number.replace("/", "-") not in checked:
                    found.append({"label": f"Sprawdź KW {number}", "say": f"sprawdź KW {number}",
                                  "why": "numer księgi jest w dokumentach, a jej treści nie ma w sprawie"})
                    break
            if pesels_in(body) and "KRZ (" not in checked:
                found.append({"label": "Sprawdź strony w KRZ", "say": "sprawdź strony w KRZ",
                              "why": "w dokumentach są numery PESEL, a sprawdzenia w KRZ jeszcze nie było"})
            if names and not any(n.lower().endswith(".docx") for n in names):
                found.append({"label": "Przygotuj projekt aktu", "say": "przygotuj projekt aktu na podstawie dokumentów sprawy",
                              "why": "sprawa ma dokumenty, ale nie ma jeszcze projektu aktu"})
        me = norm(self.who(identity))
        since = self._read_messages.get(identity.id, 0)
        fresh = [m for m in s.vault.messages(50) if m.get("created", 0) > since and norm(m.get("from", "")) != me
                 and (norm(m.get("to", "")) in {me, "wszyscy", "wszystkich", "kancelaria"} or me in norm(m.get("to", "")))]
        if fresh:
            found.insert(0, {"label": f"Nowe wiadomości ({len(fresh)})", "say": "wiadomości",
                             "why": f"od: {', '.join(sorted({m['from'] for m in fresh}))}"})
        if identity.scope == "admin" and s.settings().mail.source is not None:
            found.append({"label": "Przejrzyj pocztę", "say": "poczta", "why": "poczta jest podłączona"})
        try:
            waiting = len(s.learning.pending())
        except Exception:
            waiting = 0
        if waiting:
            found.append({"label": f"Potwierdź lekcje ({waiting})", "say": "lekcje do potwierdzenia",
                          "why": "tryb uczenia czeka na Twoje „tak” albo „nie”"})
        if identity.scope == "admin":
            last = s.status().get("last_backup")
            if s.status().get("enrolled") and (not last or time.time_ns() - last > 7 * 86400 * 10**9):
                found.append({"label": "Zrób kopię sejfu", "say": "zrób kopię", "why": "ostatnia kopia jest starsza niż tydzień"})
        unique, seen = [], set()
        for item in found:
            if item["say"] not in seen:
                seen.add(item["say"])
                unique.append(item)
        return unique[:3]

    # ------------------------------------------------------------ learning mode
    def _learning(self, identity, message, plain):
        from .learning import KINDS

        s = self.s
        learning = s.learning
        writable = identity.scope in {"admin", "write"}
        if plain in {"tryb uczenia", "uczenie", "czy sie uczysz", "czy sie uczysz?"}:
            summary = learning.summary()
            state = "włączony" if summary["enabled"] else "wyłączony"
            lines = [f"Tryb uczenia: {state}. Znam lekcji: {summary['total']}."]
            lines += [f"• {KINDS[k]}: {n}" for k, n in summary["counts"].items() if n]
            lines.append("Uczę się z: poprawek w projektach aktów, poprawek po dyktowaniu, Twoich odpowiedzi na maile, "
                         "poleceń „zapamiętaj: …” i „to było źle: …”. Każdą lekcję widzisz i możesz usunąć.")
            actions = [("Czego się nauczyłeś?", "czego się nauczyłeś")]
            if identity.scope == "admin":
                actions.append(("Wyłącz tryb uczenia", "wyłącz tryb uczenia") if summary["enabled"] else
                               ("Włącz tryb uczenia", "włącz tryb uczenia"))
            return [text("\n".join(lines)), buttons(*actions)]
        if plain in {"pytaj o potwierdzenie", "pytaj przed wykonaniem", "nie pytaj o potwierdzenie", "wykonuj bez pytania",
                     "potwierdzenia", "wlacz potwierdzenia", "wylacz potwierdzenia"}:
            if identity.scope != "admin":
                return [text("To ustawia się na komputerze kancelarii.")]
            if plain == "potwierdzenia":
                asks = s.settings().confirm
                return [text("Teraz " + ("pytam „Tak / Nie” przed nieodwracalnymi czynnościami." if asks else
                                         "wykonuję polecenia od razu: polecenie jest zatwierdzeniem.")),
                        buttons(("Nie pytaj", "nie pytaj o potwierdzenie") if asks else ("Pytaj o potwierdzenie", "pytaj o potwierdzenie"))]
            asks = plain in {"pytaj o potwierdzenie", "pytaj przed wykonaniem", "wlacz potwierdzenia"}
            s.update_settings(lambda d: d.update(confirm=asks))
            return [text("Od teraz pytam „Tak / Nie” przed wysyłką, pobraniem płatnym i usuwaniem." if asks else
                         "Od teraz polecenie jest zatwierdzeniem: „wyślij pocztę” wysyła od razu. Wykonane czynności "
                         "zawsze pokazuję w rozmowie z dokładną treścią.")]
        if plain in {"wlacz tryb uczenia", "wylacz tryb uczenia", "wlacz uczenie", "wylacz uczenie"}:
            if identity.scope != "admin":
                return [text("Tryb uczenia przełącza się na komputerze kancelarii.")]
            on = plain.startswith("wlacz")
            s.update_settings(lambda d: d.update(learn=on))
            return [text("Tryb uczenia włączony: uczę się z Twoich poprawek i poleceń, a każdą lekcję pokazuję." if on else
                         "Tryb uczenia wyłączony: nie zapisuję nowych lekcji i nie używam dotychczasowych."),
                    {"type": "learning"}]
        if plain in {"lekcje do potwierdzenia", "co do potwierdzenia", "potwierdz lekcje", "nowe lekcje"}:
            waiting = learning.pending()
            if not waiting:
                return [text("Nie ma nowych lekcji do potwierdzenia.")]
            return [{"type": "lessons", "items": [{"id": l["id"], "text": l["text"]} for l in waiting[:12]]}]
        found = re.fullmatch(r"(potwierdz|odrzuc) lekcje\s+([0-9a-f]{12})", plain)
        if found:
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            decided = learning.decide(found.group(2), found.group(1) == "potwierdz", actor=identity.id)
            if decided is None:
                return [text("Nie ma takiej lekcji.")]
            return [text(("📘 Potwierdzone, będę z tego korzystać: " if decided["status"] == "potwierdzona"
                          else "Odrzucone, nie będę się tego trzymać: ") + decided["text"]), {"type": "learning"}]
        if plain in {"czego sie nauczyles", "czego sie nauczyles?", "lekcje", "co wiesz o kancelarii", "pokaz lekcje"}:
            lessons = learning.lessons()
            self._lessons[identity.id] = lessons
            if not lessons:
                return [text("Nie mam jeszcze żadnych lekcji. Uczę się, gdy poprawiasz projekty, dyktujesz i odpowiadasz "
                             "na maile, albo gdy napiszesz „zapamiętaj: …”.")]
            lines, number = [], 0
            for kind, title in KINDS.items():
                group = [l for l in lessons if l["kind"] == kind]
                if group:
                    lines.append(title + ":")
                    for lesson in group:
                        number += 1
                        lines.append(f"{number}. {lesson['text']}" + (f" (×{lesson['seen']})" if lesson.get("seen", 1) > 1 else "")
                                     + (" [czeka na potwierdzenie]" if lesson.get("status") == "proponowana" else ""))
            self._lessons[identity.id] = [l for kind in KINDS for l in lessons if l["kind"] == kind]
            return [text("\n".join(lines)), text("Żeby usunąć lekcję, napisz „zapomnij lekcję” i numer.")]
        found = re.fullmatch(r"zapomnij(?: lekcj[eaę])?\s+(\d+)", plain)
        if found:
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            listed = self._lessons.get(identity.id) or []
            index = int(found.group(1))
            if not 1 <= index <= len(listed):
                return [text("Nie ma lekcji o tym numerze. Napisz „czego się nauczyłeś”.")]
            lesson = listed[index - 1]

            def forget():
                learning.forget(lesson["id"], actor=identity.id)
                return [text(f"Zapomniałem: {lesson['text']}")]
            return [self._confirm(identity, f"Zapomnieć lekcję „{lesson['text'][:160]}”?", "Tak, zapomnij", forget)]
        found = re.match(r"(zapamietaj|zapisz w pamieci|pamietaj)\b\s*(?:ze|:)?\s*", plain)
        if found and len(plain) > found.end():
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            content = message[len(message) - (len(plain) - found.end()):].strip(" :")
            lesson = learning.remember(content, "wiedza")
            return [text("📘 Zapamiętałem: " + content if lesson else "To już wiem."), {"type": "learning"}]
        found = re.match(r"(to bylo zle|zle|nie tak|popraw sie|blad)\s*[:,-]\s*", plain)
        if found and len(plain) > found.end():
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            content = message[len(message) - (len(plain) - found.end()):].strip()
            learning.remember(content, "korekta")
            return [text("📘 Dziękuję, zapamiętałem korektę: " + content + ". Będę ją brał pod uwagę w kolejnych odpowiedziach."),
                    {"type": "learning"}]
        return None

    # ------------------------------------------------------------ public registers: EKW and KRZ
    def _registers(self, identity, message, plain, case):
        from .registers import KW, land_register_numbers, pesels_in

        kw_asked = re.match(r"(sprawdz|pobierz|otworz|pokaz|odczytaj)? ?(kw|ksiege|ksiega|ksiegi|ksiege wieczysta|tresc kw|odpis kw)\b", plain)
        krz_asked = re.search(r"\bkrz\b|rejestr\w* zadluzonych", plain) and plain.startswith(("sprawdz", "krz", "przeszukaj", "szukaj"))
        if not kw_asked and not krz_asked:
            return None
        s = self.s
        if identity.scope not in {"admin", "write"}:
            return [text("To urządzenie ma dostęp tylko do odczytu.")]
        if case is None or not s.may_see_case(identity, case):
            return [text("Najpierw wybierz sprawę: wynik zapiszę w jej dokumentach.")]
        if kw_asked:
            found = KW.search(message.upper())
            if not found:
                numbers = land_register_numbers(s.drafts.case_text(case, identity.id))
                if not numbers:
                    return [text("Podaj numer księgi, np. „sprawdź KW WA1M/00012345/6”. W dokumentach tej sprawy "
                                 "nie znalazłem żadnego numeru.")]
                return [text("Którą księgę pobrać? Znalazłem w dokumentach sprawy:"),
                        buttons(*[(n, f"sprawdź KW {n}") for n in numbers[:8]])]
            number = found.group(1).upper()

            def fetch():
                job = s.start_job(identity, lambda: self._land_register(identity, case, number))
                return [text(f"Pobieram treść księgi {number}. To trwa zwykle 1-4 minuty; możesz w tym czasie pracować, "
                             "wynik pojawi się tutaj i w dokumentach sprawy."), {"type": "job", "id": job}]
            return [self._confirm(identity, f"Pobrać treść księgi {number} do sprawy „{case}”? Zapytanie u dostawcy "
                                  "jest płatne; to nie jest odpis urzędowy, porównaj go ze źródłem.", "Tak, pobierz", fetch)]
        pesels = pesels_in(message) or pesels_in(s.drafts.case_text(case, identity.id))
        if not pesels:
            return [text("Nie znalazłem numerów PESEL w dokumentach tej sprawy. Napisz „sprawdź KRZ” i numer PESEL.")]
        masked = ", ".join(p[:4] + "*******" for p in pesels[:6])

        def search():
            job = s.start_job(identity, lambda: self._debtors(identity, case, pesels[:6]))
            return [text(f"Sprawdzam w KRZ: {masked}. Każda osoba to dwa wyszukiwania z odstępem; wynik i zrzuty "
                         "trafią do sprawy."), {"type": "job", "id": job}]
        return [self._confirm(identity, f"Sprawdzić w Krajowym Rejestrze Zadłużonych osoby o numerach {masked} "
                              f"(sprawa „{case}”)? Przeglądarka NotarAI otworzy krz.ms.gov.pl.", "Tak, sprawdź", search)]

    def _land_register(self, identity, case, number) -> list[dict]:
        s = self.s
        s.narrate(identity, f"Łączę się z usługą ksiąg wieczystych we Frankfurcie i proszę o księgę {number}.")
        answer = s.registers.land_register(number)
        s.narrate(identity, "Mam treść działów. Zapisuję ją w sprawie i przygotowuję podsumowanie.")
        book = answer["ksiega"]
        name = f"KW {number.replace('/', '-')} ({time.strftime('%Y-%m-%d')}).txt"
        doc_id, version = s.vault.put(None, 0, name, answer["tekst"].encode(), actor=identity.id, case=case)
        lines = [f"Księga {number}" + (f", {book.get('sad')}" if book.get("sad") else "") + "."]
        for section in book.get("dzialy", []):
            first = (section.get("tekst") or "").strip().splitlines()[:1]
            lines.append(f"• Dział {section['oznaczenie']}: " + ("brak wpisów" if section.get("pusty") else
                                                                (first[0][:120] if first else "wpisy w dokumencie")))
        lines.append("Pełna treść jest w dokumentach sprawy. To nie jest odpis urzędowy.")
        return [text("\n".join(lines)), {"type": "documents", "items": [{"id": doc_id, "name": name, "version": version}]},
                buttons(("Porównaj z dokumentami sprawy", f"porównaj księgę {number} z dokumentami sprawy: strony, "
                                                          "obciążenia w dziale III i IV, oznaczenie nieruchomości"),
                        ("Otwórz", f"otwórz {name}"))]

    def _debtors(self, identity, case, pesels) -> list[dict]:
        s = self.s
        words = {"brak_wpisu": "brak wpisu", "wpis": "ZNALEZIONO POZYCJĘ, sprawdź zrzut", "blad": "nie rozpoznano wyniku, sprawdź zrzut"}
        lines, items = [], []
        for pesel in pesels:
            s.narrate(identity, f"Sprawdzam w KRZ osobę {pesel[:4]}*******: dwie zakładki, z odstępem.")
            result = s.registers.debtors(pesel)
            lines.append(f"• {result['maska']}: {words.get(result['status'], result['status'])}")
            for shot_name, data in result.get("zrzuty", []):
                doc_id, version = s.vault.put(None, 0, shot_name, data, actor=identity.id, case=case)
                items.append({"id": doc_id, "name": shot_name, "version": version})
        note = (f"Sprawdzenie w KRZ ({result['zrodlo']}), {time.strftime('%Y-%m-%d %H:%M')}:\n" + "\n".join(lines)
                + "\nWynik heurystyczny: zawsze do potwierdzenia na zrzutach.")
        name = f"KRZ ({time.strftime('%Y-%m-%d %H-%M')}).txt"
        doc_id, version = s.vault.put(None, 0, name, note.encode(), actor=identity.id, case=case)
        items.insert(0, {"id": doc_id, "name": name, "version": version})
        return [text(note), {"type": "documents", "items": items}]

    # ------------------------------------------------------------ calendar
    def _calendar(self, identity, message, plain, case, writable):
        from .terminarz import parse_when

        calendar = self.s.calendar
        if plain in {"kalendarz", "terminy", "terminarz", "plan", "plan dnia", "co mam dzis", "co dzis", "co mam dzisiaj",
                     "najblizsze terminy", "pokaz kalendarz", "pokaz terminy", "co mam w tym tygodniu"}:
            days = 1 if "dzis" in plain or plain == "plan dnia" else 14
            return self._agenda(identity, calendar.upcoming(days, cases=identity.cases),
                                "dziś" if days == 1 else "w najbliższych dwóch tygodniach")
        if plain in {"co mam jutro", "co jutro", "jutro", "plan na jutro", "terminy jutro"}:
            tomorrow = calendar.now().date() + __import__("datetime").timedelta(days=1)
            return self._agenda(identity, calendar.upcoming(1, cases=identity.cases, start=tomorrow), "jutro")
        if plain in {"dodaj termin", "nowy termin", "zapisz termin", "wpisz termin"}:
            return [text("Napisz termin zdaniem, np. „termin jutro 10:00 podpisanie aktu Kowalski”, „termin w piątek "
                         "o 12 Nowak” albo „termin 5 grudnia 9:30 odbiór wypisu”.")]
        found = re.fullmatch(r"(?:dodaj termin|nowy termin|termin|umow|zapisz termin|wpisz termin|przypomnij)\s*:?\s+(.+)",
                             message, re.IGNORECASE | re.DOTALL)
        if found and norm(message).startswith(("dodaj termin", "nowy termin", "termin", "umow", "zapisz termin",
                                               "wpisz termin", "przypomnij")):
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            parsed = parse_when(found.group(1), calendar.now())
            if parsed is None and norm(message).startswith("termin "):
                return None       # "termin płatności w umowie?" is a question about the case, not an appointment
            if parsed is None:
                return [text("Kiedy? Napisz np. „termin w piątek 10:00 podpisanie aktu Kowalski” albo "
                             "„termin 5 grudnia o 9:30 Nowak”.")]
            start, what = parsed
            if case is not None and not self.s.may_see_case(identity, case):
                case = None
            entry = calendar.add(start, what, case=case, actor=identity.id)
            from .terminarz import label
            return [text(f"Zapisałem w kalendarzu: {label(start, calendar.now())}, {entry['title']}"
                         + (f" (sprawa „{case}”)." if case else ".")),
                    {"type": "calendar"}, buttons(("Kalendarz", "kalendarz"), ("Cofnij", f"usuń termin {entry['id']}"))]
        found = re.fullmatch(r"(?:usun|skasuj|odwolaj) termin\s+(.+)", plain)
        if found:
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            listed = self._agendas.get(identity.id, [])
            key = found.group(1).strip()
            hit = next((e for e in calendar.upcoming(366, cases=identity.cases) if e["id"] == key), None)
            if hit is None and key.isdigit() and 0 < int(key) <= len(listed):
                hit = listed[int(key) - 1]
            if hit is None:
                return [text("Nie ma takiego terminu. Napisz „kalendarz”, żeby zobaczyć numery.")]

            def remove():
                calendar.delete(hit["id"], actor=identity.id)
                return [text(f"Usunąłem termin: {hit['label']}, {hit['title']}."), {"type": "calendar"}]
            return [self._confirm(identity, f"Usunąć termin {hit['label']}, {hit['title']}?", "Tak, usuń", remove)]
        return None

    def _agenda(self, identity, items, span: str) -> list[dict]:
        self._agendas[identity.id] = items
        if not items:
            return [text(f"Brak terminów {span}. Dodasz zdaniem, np. „termin jutro 10:00 podpisanie aktu Kowalski”.")]
        lines = [f"{i}. {e['label']}  {e['title']}" + (f"  [{e['case']}]" if e.get("case") else "")
                 for i, e in enumerate(items, 1)]
        return [text(f"Terminy {span}:\n" + "\n".join(lines)),
                buttons(("Co mam jutro", "co mam jutro"), ("Dodaj termin", "dodaj termin "))]

    # ------------------------------------------------------------ where the office's data lives
    EVERY = {"co godzine": 1, "co 6 godzin": 6, "co szesc godzin": 6, "raz na dobe": 24, "codziennie": 24,
             "co dobe": 24, "raz w tygodniu": 168, "co tydzien": 168}
    KEEP = {"30 dni": 30, "miesiac": 30, "90 dni": 90, "3 miesiace": 90, "rok": 365, "1 rok": 365,
            "bez usuwania": 0, "zawsze": 0, "na zawsze": 0}

    def _where(self, identity, plain):
        s = self.s
        if plain in {"gdzie sa dane", "gdzie dane", "gdzie sa moje dane", "przechowywanie", "przechowywanie danych",
                     "dane", "ustawienia danych", "gdzie trzymamy dane", "mowa"}:
            return self._where_summary()
        if plain in {"mowa na tym komputerze", "mowa lokalnie", "przepisuj na tym komputerze", "mowa na komputerze"}:
            if not s.local_speech_installed():
                return [text("Na tym komputerze brakuje modułu rozpoznawania mowy. Zainstaluj NotarAI ponownie "
                             "z linku do pobrania, a potem napisz to jeszcze raz.")]
            s.update_settings(lambda d: d["speech"].update(where="lokalnie"))
            s.onboarding.mark("dane")
            s.download_speech_model()
            return [text("Od teraz mowę przepisuje ten komputer i dźwięk nie wychodzi z kancelarii. Najpierw pobiorę "
                         "model mowy (raz, ok. 0,5 GB). Postęp widać poniżej; w tym czasie możesz normalnie pracować. "
                         "Przepisywanie zajmie tu więcej czasu niż we Frankfurcie i obciąży procesor."),
                    {"type": "progress", "source": "speech/model"}]
        if plain in {"mowa we frankfurcie", "mowa w chmurze", "przepisuj we frankfurcie", "przepisuj w chmurze"}:
            s.update_settings(lambda d: d["speech"].update(where="chmura"))
            s.onboarding.mark("dane")
            return [text("Od teraz mowę przepisuje Amazon Transcribe we Frankfurcie: dźwięk jest przesyłany "
                         "strumieniem, tekst wraca po kilku sekundach, a nagranie nie jest tam zapisywane. "
                         "Nagranie i tekst zostają tylko w sejfie na tym komputerze.")]
        found = re.fullmatch(r"(?:kopia|kopie|kopie zapasowe)(?: (?:we frankfurcie|w chmurze|poza kancelaria))? (.+)", plain)
        if found and found.group(1) in self.EVERY:
            hours = self.EVERY[found.group(1)]
            settings = s.settings()
            if settings.replica.enabled:
                s.update_settings(lambda d: d["replica"].update(every_hours=hours))
                return [text(f"Kopia we Frankfurcie będzie wysyłana {self._every(hours)}.")]

            def turn_on():
                s.update_settings(lambda d: d["replica"].update(enabled=True, every_hours=hours))
                return [text(f"Kopia we Frankfurcie włączona, {self._every(hours)}. Pierwsza pójdzie w ciągu "
                             "kilkunastu minut, gdy stanowisko jest zalogowane.")]
            return [self._confirm(identity, "Wysyłać zaszyfrowaną kopię całego sejfu do Frankfurtu "
                                  f"{self._every(hours)}? Otworzy ją tylko kod odzyskiwania kancelarii; ani NotarAI, "
                                  "ani Amazon nie mają klucza.", "Tak, włącz kopię", turn_on)]
        if found and found.group(1) in {"wylacz", "wylaczona", "nie", "bez kopii"} or plain in {
                "wylacz kopie we frankfurcie", "bez kopii we frankfurcie"}:
            s.update_settings(lambda d: d["replica"].update(enabled=False))
            return [text("Kopia we Frankfurcie wyłączona. Kopie już wysłane zostają tam według ustawionego czasu.")]
        found = re.fullmatch(r"(?:trzymaj|przechowuj) kopie(?: we frankfurcie)? (.+)", plain)
        if found and found.group(1) in self.KEEP:
            days = self.KEEP[found.group(1)]
            s.update_settings(lambda d: d["replica"].update(keep_days=days))
            return [text("Kopie we Frankfurcie będą przechowywane bez usuwania." if days == 0 else
                         f"Kopie we Frankfurcie starsze niż {days} dni będą usuwane (zawsze zostają co najmniej 3 ostatnie).")]
        return None

    @staticmethod
    def _every(hours: int) -> str:
        return {1: "co godzinę", 6: "co 6 godzin", 24: "raz na dobę", 168: "raz w tygodniu"}.get(hours, f"co {hours} godz.")

    def _where_summary(self) -> list[dict]:
        s = self.s
        settings = s.settings()
        replica = settings.replica
        local = settings.speech.where == "lokalnie"
        blocks = [text(
            "Gdzie są dane tej kancelarii:\n"
            "• Dokumenty, notatki i nagrania: zawsze w zaszyfrowanym sejfie na tym komputerze.\n"
            "• Mowa: " + ("przepisuje ten komputer, dźwięk nie wychodzi z kancelarii." if local else
                          "przepisuje Frankfurt (Amazon Transcribe), strumieniem, bez zapisywania nagrania.") + "\n"
            "• Kopia sejfu we Frankfurcie: " + (
                (self._every(replica.every_hours) + ", " + (
                    "przechowywana bez usuwania" if replica.keep_days == 0 else f"przechowywana {replica.keep_days} dni")
                 + ", zaszyfrowana kodem odzyskiwania") if replica.enabled else "wyłączona") + ".\n"
            "• AI: modele w UE (Frankfurt), bez zapisywania treści i bez uczenia na danych kancelarii.")]
        blocks.append(text("Mowa:"))
        blocks.append(buttons(("Na tym komputerze", "mowa na tym komputerze"),
                              ("We Frankfurcie, bez zapisu", "mowa we frankfurcie")))
        if local:
            blocks.append({"type": "progress", "source": "speech/model"})
        blocks.append(text("Kopia sejfu we Frankfurcie:"))
        blocks.append(buttons(("Wyłączona", "kopia we frankfurcie wyłącz"), ("Co godzinę", "kopia we frankfurcie co godzinę"),
                              ("Co 6 godzin", "kopia we frankfurcie co 6 godzin"), ("Raz na dobę", "kopia we frankfurcie raz na dobę")))
        if replica.enabled:
            blocks.append(text("Jak długo trzymać kopie we Frankfurcie:"))
            blocks.append(buttons(("30 dni", "trzymaj kopie 30 dni"), ("Rok", "trzymaj kopie rok"),
                                  ("Bez usuwania", "trzymaj kopie bez usuwania")))
        return blocks

    def _mail(self, identity, message, plain, case):
        s = self.s
        if plain in {"wyslij", "wyslij odpowiedz"} and identity.id in self._replies:
            pending = self._replies[identity.id]
            if not pending[3].strip():
                return [text("Nie mam gotowej odpowiedzi do wysłania: projekt jest pusty. Napisz albo podyktuj treść "
                             "w karcie odpowiedzi, albo „odpowiedz na mail " + str(pending[0]) + ": treść”.")]
            return self._send_reply(identity, pending[1], pending[2], pending[3])
        if not re.search(r"\b(poczt\w*|mail\w*|maile|wiadomosc\w*|skrzynk\w*|outlook\w*|thunderbird\w*|zalacznik\w*)\b", plain):
            return None
        if plain.startswith(("odlacz poczte", "wylacz poczte", "rozlacz poczte")):
            s.update_settings(lambda d: d["mail"].update(source=None, path=None))
            self._inbox.pop(identity.id, None)
            return [text("Odłączyłem pocztę. Nie czytam już wiadomości z tego komputera.")]
        if plain.startswith(("polacz", "podlacz", "sparuj", "dodaj poczte", "wlacz poczte")):
            found = re.search(r"folder\s+(.+)", message, re.IGNORECASE)
            if found:
                choice, path = "folder", found.group(1).strip().strip("\"„”")
            else:
                available = {source.name.lower(): source for source in s.mail_detect()}
                named = next((name for name in ("thunderbird", "outlook") if name in plain), None)
                if named and named not in available:
                    return [text(f"Nie znalazłem programu {named.capitalize()} na tym komputerze.")]
                if not named and len(available) > 1:
                    return [text("Znalazłem dwa programy pocztowe. Który podłączyć?"),
                            buttons(*[(name.capitalize(), f"połącz pocztę {name}") for name in available])]
                if not named and not available:
                    return [text("Nie znalazłem Thunderbirda ani klasycznego Outlooka. W innym programie zapisz "
                                 "wiadomości do folderu (pliki .eml) i napisz „połącz pocztę folder” ze ścieżką, "
                                 "np. „połącz pocztę folder C:\\Poczta”.")]
                choice = named or next(iter(available))
                path = getattr(available[choice], "location", None)
            s.update_settings(lambda d: d["mail"].update(source=choice, path=path))
            source = s.mail_source()
            if source is None or not source.available():
                s.update_settings(lambda d: d["mail"].update(source=None, path=None))
                return [text("Nie udało się otworzyć tej poczty. Sprawdź ścieżkę albo czy program jest zainstalowany.")]
            label = "folderu z wiadomościami" if choice == "folder" else choice.capitalize()
            return [text(f"Połączyłem pocztę z {label}. Tylko czytam, na tym komputerze; wiadomość trafia do sejfu "
                         "dopiero, gdy dodasz ją do sprawy."), buttons(("Pokaż pocztę", "poczta"))]
        source = s.mail_source()
        if source is None:
            return [text("Poczta nie jest jeszcze połączona."), buttons(("Połącz pocztę", "połącz pocztę"))]
        found = re.fullmatch(r"dodaj (?:mail|maila|wiadomosc)\s+(\d+)(?: do sprawy)?(?:\s+(\S+))?", plain)
        if found:
            target = message.split()[-1] if found.group(2) else case
            listed = self._inbox.get(identity.id) or []
            index = int(found.group(1))
            if not 1 <= index <= len(listed):
                return [text("Nie ma wiadomości o tym numerze. Napisz „poczta”, żeby zobaczyć listę.")]
            if target is None or not valid_case(target):
                return [text("Do której sprawy? Wybierz sprawę u góry albo napisz „dodaj mail 1 do sprawy nazwa”.")]
            name, data = as_document(listed[index - 1])
            doc_id, version = s.vault.put(None, 0, name, data, actor=identity.id, case=target)
            return [text(f"Dodałem wiadomość do sprawy „{target}”. Asystent będzie ją czytał razem z innymi dokumentami."),
                    {"type": "documents", "items": [{"id": doc_id, "name": name, "version": version}]}]
        found = re.fullmatch(r"dodaj zalacznik\s+(\d+)\s+z (?:maila|mail|wiadomosci)\s+(\d+)(?: do sprawy)?", plain)
        if found:
            if identity.scope not in {"admin", "write"}:
                return [text("To urządzenie ma dostęp tylko do odczytu.")]
            listed = self._inbox.get(identity.id) or []
            index = int(found.group(2))
            if not 1 <= index <= len(listed):
                return [text("Nie ma wiadomości o tym numerze. Napisz „poczta”, żeby zobaczyć listę.")]
            if case is None:
                return [text("Do której sprawy? Wybierz sprawę u góry i kliknij załącznik jeszcze raz.")]
            from .mail import attachment
            name, data = attachment(listed[index - 1], int(found.group(1)) - 1, source)
            doc_id, version = s.vault.put(None, 0, name, data, actor=identity.id, case=case)
            readable = name.lower().endswith((".docx", ".pdf", ".txt", ".eml"))
            return [text(f"Dodałem załącznik {name} do sprawy „{case}”." + (" Co z nim zrobić?" if readable else "")),
                    {"type": "documents", "items": [{"id": doc_id, "name": name, "version": version}]}] + (
                    [buttons(("Streść", f"streść {name}"), ("Sprawdź błędy", f"sprawdź {name}"))] if readable else [])
        found = re.fullmatch(r"odpowiedz(?: na)? (?:mail|maila|wiadomosc)\s+(\d+)(?:\s*:\s*(.+))?", plain)
        if found and found.group(2):
            found = re.fullmatch(r"(?i)odpowiedz\w*(?: na)? (?:mail\w*|wiadomo\w*)\s+(\d+)\s*:\s*(.+)", message, re.S) or found
        if found:
            listed = self._inbox.get(identity.id) or []
            index = int(found.group(1))
            if not 1 <= index <= len(listed):
                return [text("Nie ma wiadomości o tym numerze. Napisz „poczta”, żeby zobaczyć listę.")]
            mail = listed[index - 1]
            draft = ""
            s.narrate(identity, f"Czytam wiadomość „{mail.subject[:60]}” i piszę projekt odpowiedzi w tonie kancelarii.")
            try:
                draft = s.general("Napisz krótką, uprzejmą i rzeczową odpowiedź kancelarii notarialnej na poniższą "
                                  "wiadomość. Tylko treść odpowiedzi, bez tematu i bez podpisu.\n\n"
                                  f"Od: {mail.sender}\nTemat: {mail.subject}\n\n{mail.text[:6000]}",
                                  [mail.sender] if mail.sender else [], mail=True)["answer"]
            except Exception:
                draft = ""              # no assistant here: the notary writes or dictates the reply
            subject = mail.subject if norm(mail.subject).startswith(("re:", "odp:")) else "Re: " + mail.subject
            if found.group(2):                    # „odpowiedz na mail 2: treść” - the command is the approval
                return self._send_reply(identity, mail, subject, found.group(2).strip())
            self._replies[identity.id] = (index, mail, subject, draft)
            return [{"type": "reply", "n": index, "to": mail.address, "subject": subject, "body": draft,
                     "program": source.name}]
        if plain in {"wyslij", "wyslij poczte", "wyslij odpowiedz", "wyslij maila", "wyslij mail", "wyslij wiadomosc"}:
            pending = self._replies.get(identity.id)
            if pending is None or not pending[3].strip():
                return [text("Nie mam gotowej odpowiedzi do wysłania. Napisz „odpowiedz na mail” i numer albo "
                             "„odpowiedz na mail 2: treść”.")]
            return self._send_reply(identity, pending[1], pending[2], pending[3])
        found = re.fullmatch(r"(?:pokaz |otworz |przeczytaj )?(?:mail|maila|wiadomosc)\s+(\d+)", plain)
        if found:
            listed = self._inbox.get(identity.id) or []
            index = int(found.group(1))
            if not 1 <= index <= len(listed):
                return [text("Nie ma wiadomości o tym numerze. Napisz „poczta”, żeby zobaczyć listę.")]
            mail = listed[index - 1]
            body = mail.text[:3000] + ("\n[…]" if len(mail.text) > 3000 else "")
            head = f"Od: {mail.sender} <{mail.address}>\nTemat: {mail.subject}"
            if mail.attachments:
                head += "\nZałączniki: " + ", ".join(mail.attachments)
            actions = [(f"Dodaj do sprawy{' „' + case + '”' if case else ''}", f"dodaj mail {index} do sprawy"),
                       ("Odpowiedz", f"odpowiedz na mail {index}")]
            actions += [(f"📎 {name[:40]} do sprawy", f"dodaj załącznik {k} z maila {index}")
                        for k, name in enumerate(mail.attachments[:8], 1)]
            return [text(head + "\n\n" + body), buttons(*actions)]
        listed = source.latest(30)
        sender = re.search(r"\bod\s+(.+)", plain)
        if sender:
            wanted = sender.group(1).strip(" ?")
            listed = [m for m in listed if wanted in norm(m.sender) or wanted in norm(m.address)]
        listed = listed[:8]
        self._inbox[identity.id] = listed
        if not listed:
            return [text("Nie ma takich wiadomości." if sender else "Skrzynka odbiorcza jest pusta.")]
        lines = [f"{n}. {when(int(m.when * 10**9))}, {m.sender or m.address}: {m.subject or '(bez tematu)'}"
                 + (" 📎" if m.attachments else "") for n, m in enumerate(listed, 1)]
        return [{"type": "inbox", "text": "\n".join(lines), "items": [
            {"n": n, "sender": m.sender or m.address, "subject": m.subject or "(bez tematu)",
             "when": when(int(m.when * 10**9)), "attachments": len(m.attachments)} for n, m in enumerate(listed, 1)]}]

    def _send_reply(self, identity, mail, subject: str, body: str) -> list[dict]:
        if identity.scope != "admin":
            return [text("Pocztę wysyła komputer kancelarii: napisz to w oknie NotarAI na tym komputerze.")]
        result = self.s.send_mail(identity, mail.address, subject, body, mail)
        self._replies.pop(identity.id, None)
        blocks = [text(result["detail"] + f"\nDo: {mail.address}\nTemat: {subject}\n\n{body}")]
        if result["learned"]:
            blocks.append({"type": "lessons", "items": result["learned"]})   # [{id, text}]
        return blocks

    def inbox_message(self, identity, index: int):
        listed = self._inbox.get(identity.id) or []
        return listed[index - 1] if 1 <= index <= len(listed) else None

    def _programs(self) -> list[dict]:
        s = self.s
        mail = s.mail_source()
        known = len(s.procedures.list())
        lines = [
            "Tak pracuję z programami na tym komputerze:",
            "• Word i LibreOffice: „otwórz umowa w Wordzie”, potem „zapisz do sejfu”.",
            "• Poczta: " + ("połączona." if mail is not None else "niepołączona; napisz „połącz pocztę” (Thunderbird, Outlook albo folder)."),
            f"• Każdy inny program i każda strona urzędowa: pokaż mi raz, jak wypełniasz formularz (nagranie ekranu "
            f"z komentarzem), a będę przygotowywać wartości dla kolejnych spraw. Znam procedur: {known}.",
            "Wypełniam sam: na stronach w przeglądarce NotarAI, w programach Windows przez to samo, z czego "
            "korzystają czytniki ekranu. Wysyłam dopiero po Twoim zatwierdzeniu wypełnionego formularza.",
        ]
        return [text("\n".join(lines)),
                buttons(("Nagraj procedurę", "nagraj procedurę"), ("Procedury", "procedury"),
                        ("Połącz pocztę", "połącz pocztę"))]

    def _status(self) -> list[dict]:
        st = self.s.status()
        lines = [
            "Tryb próbny: tylko fikcyjne dokumenty." if st["mode"] == "synthetic-only" else "Dokumenty kancelarii są na tym komputerze.",
            f"Dokumentów: {st['documents']}, spraw: {st['cases']}, sparowanych urządzeń: {st['devices']}.",
            "Kod odzyskiwania: jest." if st["enrolled"] else "Kod odzyskiwania: BRAK.",
            ("Ostatnia kopia: " + when(st["last_backup"]) + ".") if st["last_backup"] else "Kopii zapasowej jeszcze nie było.",
            "Kopia poza kancelarią: " + (("włączona, ostatnia " + when(st["last_offsite"])) if st["last_offsite"]
                                         else "włączona, jeszcze nie wysłana" if st["offsite"] else "wyłączona") + ".",
            "Asystent: " + ("zalogowany" if st["signed_in"] else "niezalogowany" if st["ai"] else "brak konta NotarAI na stanowisku")
            + ("; pseudonimizacja włączona." if st["pseudonymize"] else "; pseudonimizacja wyłączona."),
            "Dostęp spoza kancelarii: " + ("połączony z przekaźnikiem." if st["tunnel_connected"]
                                           else "włączony, brak połączenia." if st["tunnel"] else "wyłączony."),
        ]
        return [text("\n".join(lines))] + self._warnings(True)

    def _recovery_code(self, replace: bool) -> list[dict]:
        code = self.s.enroll(replace)
        return [{"type": "secret", "title": "Kod odzyskiwania sejfu NotarAI", "text": code, "print": True,
                 "hint": "Wydrukuj i przechowuj poza komputerem, np. w kasie pancernej. Nie pokażę go ponownie."},
                text("Bez tego kodu kopia jest bezużyteczna dla każdego, także dla nas.")]

    def _backup(self) -> list[dict]:
        s = self.s
        if not s.status()["enrolled"]:
            return [text("Najpierw utwórz kod odzyskiwania: bez niego kopii nie da się odtworzyć."),
                    buttons(("Utwórz kod odzyskiwania", "kod odzyskiwania"))]
        done = []
        if s.backup_dir():
            made = s.local_backup()
            done.append(f"Kopia zapisana na dysku: {made['file']} (dokumentów: {made['documents']}, wersji: {made['revisions']}).")
        if s.offsite_enabled():
            made = s.offsite_backup()
            done.append(f"Zaszyfrowana kopia wysłana poza kancelarię: {made['file']}.")
        if not done:
            return [text("Nie wiem jeszcze, gdzie zapisywać kopie. Napisz „katalog kopii” i ścieżkę do innego dysku, "
                         "np. „katalog kopii E:\\NotarAI-kopie”.")]
        return [text("\n".join(done))]

    def _devices(self, identity) -> list[dict]:
        devices = [d for d in self.s.devices.list() if not d["revoked"]]
        if not devices:
            return [text("Nie ma sparowanych urządzeń."), buttons(("Dodaj telefon", "dodaj telefon"))]
        lines = [f"• {d['name']}: {'odczyt i zapis' if d['scope'] == 'write' else 'tylko odczyt'}, "
                 + ("sprawy: " + ", ".join(d["cases"]) if d["cases"] else "wszystkie sprawy") for d in devices]
        return [text("\n".join(lines)), buttons(*[(f"Cofnij: {d['name']}", f"cofnij {d['name']}") for d in devices[:8]])]

    def _invite(self, message, plain) -> list[dict]:
        scope = "read" if re.search(r"tylko (?:do )?odczyt|bez zapisu|do odczytu", plain) else "write"
        cases = re.findall(r"spraw[ayę]?\s+([\w.-]+)", message, re.IGNORECASE)
        cases = [c for c in cases if valid_case(c) and norm(c) not in {"i", "oraz"}] or None
        named = re.search(r"(?:o nazwie|nazwa|pod nazwa)\s+[„\"]?([^„”\",]+)", message, re.IGNORECASE)
        name = named.group(1).strip() if named else {"dodaj tablet": "Tablet", "dodaj laptop": "Laptop"}.get(
            " ".join(plain.split()[:2]), "Telefon")
        existing = {d["name"] for d in self.s.devices.list()}
        base, index = name, 2
        while name in existing:
            name, index = f"{base} {index}", index + 1
        invitation = self.s.devices.invite(name, scope, cases=cases)
        what = ("tylko odczyt" if scope == "read" else "odczyt i zapis") + (
            ", sprawy: " + ", ".join(cases) if cases else ", wszystkie sprawy")
        blocks = [text(f"Urządzenie „{name}” ({what}). Kod działa raz, przez 5 minut.")]
        link = self.s.pairing_link(invitation["code"])
        if link:
            blocks += [text("Poza kancelarią: zeskanuj kod aparatem telefonu."), {"type": "qr", "link": link},
                       text("Na tym komputerze: wklej poniższy kod w Pocket.")]
        blocks.append({"type": "secret", "title": "Kod parowania", "text": invitation["code"],
                       "hint": "Nie wysyłaj go e-mailem ani komunikatorem."})
        return blocks

    def _revoke(self, identity, fragment) -> list[dict]:
        fragment = fragment.replace("cofnij: ", "").strip(" :")
        hits = [d for d in self.s.devices.list() if not d["revoked"] and fragment in norm(d["name"])]
        exact = [d for d in hits if norm(d["name"]) == fragment]
        if len(exact) != 1 and len(hits) != 1:
            return [text("Które urządzenie?" if hits else "Nie ma takiego urządzenia.")] + (
                [buttons(*[(d["name"], f"cofnij {d['name']}") for d in hits[:8]])] if hits else [])
        device = (exact or hits)[0]

        def act():
            self.s.devices.revoke(device["id"])
            self.s.vault.log(identity.id, "revoke-device")
            return [text(f"Cofnąłem dostęp urządzenia „{device['name']}”. "
                         "Plików, które już na nie pobrano, nie da się usunąć zdalnie.")]
        return [self._confirm(identity, f"Cofnąć dostęp urządzenia „{device['name']}”?", "Tak, cofnij dostęp", act)]

    def _audit(self, identity, case, plain) -> list[dict]:
        s = self.s
        names = {d["id"]: d["name"] for d in s.vault.summaries()}
        devices = {d["id"]: d["name"] for d in s.devices.list()}
        target = None
        rest = re.sub(r"^(dziennik|kto czytal|kto otwieral|historia|kto zmienial)\s*", "", plain).strip(" ?")
        if rest:
            match = self._find_document(identity, case, rest)
            if isinstance(match, dict):
                target = match["id"]
        verbs = {"read": "odczytał", "write": "zapisał", "checkout": "otworzył do edycji",
                 "discard-workcopy": "porzucił zmiany w", "backup": "zrobił kopię zapasową",
                 "offsite-backup": "wysłał kopię poza kancelarię", "calendar-put": "zapisał termin",
                 "calendar-delete": "usunął termin", "restore": "odtworzył sejf z kopii",
                 "enroll-recovery": "utworzył kod odzyskiwania", "revoke-device": "cofnął dostęp urządzenia",
                 "settings": "zmienił ustawienia", "mail-compose": "przygotował odpowiedź do wysłania", "mail-send": "wysłał wiadomość e-mail", "lesson-delete": "usunął lekcję trybu uczenia", "rotate-key": "wymienił klucz sejfu", "migrate": "przeniósł sejf do nowego formatu",
                 "form-fill-verified": "wypełnił formularz", "form-fill-partial": "wypełnił część formularza",
                 "form-send-started": "zaczął wysyłać formularz", "form-send-sent": "wysłał formularz",
                 "form-send-uncertain": "nacisnął wysyłanie formularza (wynik niepewny)"}
        who = {"local-admin": "ten komputer", "connect-verify": "kontrola po zapisie", "migration": "program"}
        lines = []
        for entry in s.vault.audit(60, target):
            if entry["actor"] == "connect-verify":
                continue
            actor = devices.get(entry["actor"]) or who.get(entry["actor"]) or "panel stanowiska"
            line = f"{when(entry['ts'])}: {actor} {verbs.get(entry['action'], entry['action'])}"
            if entry["doc_id"]:
                line += f" {names.get(entry['doc_id'], 'usunięty dokument')}" + (
                    f" (wersja {entry['version']})" if entry["version"] else "")
            lines.append(line + ".")
            if len(lines) == 15:
                break
        if not lines:
            return [text("Dziennik jest pusty.")]
        return [text("\n".join(lines)), text("Dziennik jest zabezpieczony przed zmianą wpisów.")]

    def _workcopies(self) -> list[dict]:
        copies = self.s.workcopies.list()
        if not copies:
            return [text("Żaden dokument nie jest otwarty do edycji.")]
        state = lambda c: ("plik roboczy zniknął" if c["missing"] else "otwarty w edytorze" if c["in_use"]  # noqa: E731
                           else "zmieniony, niezapisany w sejfie" if c["changed"] else "bez zmian")
        actions = []
        for copy in copies[:6]:
            actions += [(f"Zapisz do sejfu: {copy['name']}", f"zapisz do sejfu {copy['name']}"),
                        (f"Porzuć: {copy['name']}", f"porzuć zmiany {copy['name']}")]
        return [text("\n".join(f"• {c['name']}: {state(c)}" for c in copies)), buttons(*actions)]

    def _one_copy(self, fragment):
        copies = self.s.workcopies.list()
        fragment = fragment.strip(" :")
        hits = [c for c in copies if not fragment or fragment in norm(c["name"])]
        return hits[0] if len(hits) == 1 else None

    def _checkin(self, identity, fragment) -> list[dict]:
        copy = self._one_copy(fragment)
        if copy is None:
            copies = self.s.workcopies.list()
            if not copies:
                return [text("Żaden dokument nie jest otwarty do edycji.")]
            return [text("Który dokument zapisać do sejfu?"),
                    buttons(*[(c["name"], f"zapisz do sejfu {c['name']}") for c in copies[:8]])]
        result = self.s.workcopies.checkin(copy["id"], identity.id)
        return [text(f"Zapisałem {copy['name']} jako wersję {result['version']}. Kopia robocza zniknęła z dysku."
                     if result["saved"] else f"{copy['name']}: bez zmian. Kopia robocza zniknęła z dysku.")]

    def _discard(self, identity, copy) -> list[dict]:
        self.s.workcopies.discard(copy["id"], identity.id)
        return [text(f"Porzuciłem zmiany w „{copy['name']}”. Kopia robocza zniknęła z dysku.")]


__all__ = ["Chat", "DraftError", "norm", "parse_amount"]
