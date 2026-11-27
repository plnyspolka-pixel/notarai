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

    # ------------------------------------------------------------ confirmations
    def _confirm(self, identity, question: str, label: str, action) -> dict:
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
        return action()

    # ------------------------------------------------------------ entry points
    def hello(self, identity, case) -> list[dict]:
        admin = identity.scope == "admin"
        blocks = [text("Dzień dobry. Napisz, co mam zrobić, albo wybierz podpowiedź." if not admin else
                       "Dzień dobry. Tu ustawiasz to stanowisko. Napisz, co mam zrobić, albo wybierz podpowiedź.")]
        blocks += self._warnings(admin)
        if admin:
            blocks.append(buttons(("Stan stanowiska", "stan"), ("Dodaj telefon", "dodaj telefon"),
                                  ("Zrób kopię", "zrób kopię"), ("Kto czytał dokumenty?", "dziennik"),
                                  ("Dokumenty", "dokumenty"), ("Co umiesz?", "pomoc")))
        else:
            blocks.append(buttons(("Dokumenty", "dokumenty"), ("Sprawy", "sprawy"),
                                  ("Policz taksę", "taksa"), ("Co umiesz?", "pomoc")))
        return blocks

    def say(self, identity, message: str, case, names) -> list[dict]:
        message = " ".join(message.split())
        plain = norm(message)
        admin = identity.scope == "admin"
        office_rules = self._office_rules(identity, message, plain)
        if office_rules is not None:
            return office_rules
        tiles = self._tiles(identity, message, plain)       # first: a tile may be named after any command
        if tiles is not None:
            return tiles
        if admin:
            reply = self._admin(identity, message, plain, case)
            if reply is not None:
                return reply
        return self._common(identity, message, plain, case, names)

    # ------------------------------------------------------------ shared intents
    def _common(self, identity, message, plain, case, names) -> list[dict]:
        s, writable = self.s, identity.scope in {"admin", "write"}
        if plain in {"pomoc", "help", "co umiesz", "co umiesz?", "co potrafisz", "co potrafisz?"}:
            return self._help(identity.scope == "admin", writable)
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
            return [text(s.general(message, names)["answer"])]
        if not s.may_see_case(identity, case):
            return [text("Nie ma takiej sprawy.")]
        if plain.startswith(DRAFT_WORDS) or " projekt " in f" {plain} ":
            if not writable:
                return [text("To urządzenie ma dostęp tylko do odczytu, więc nie przygotuje projektu.")]
            proposal = s.drafts.propose(case, message, identity.id, names).public()
            proposal["type"] = "proposal"
            proposal["docx"] = [d for d in s.vault.summaries({case}) if d["name"].lower().endswith(".docx")]
            return [text("Projekt gotowy. Przeczytaj go; zapiszę dopiero to, co zatwierdzisz."), proposal]
        answer = s.drafts.ask(case, message, identity.id, names)
        blocks = [text(answer["answer"])]
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
            blocks.append(self._confirm(identity, f"Wysłać „{sheet['name']}” przyciskiem „{preview['send']}”? Wyślę dokładnie "
                                                  "to, co widać na zrzucie powyżej.", "Wyślij teraz", send))
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
            lines += ["• „zrób kopię”, „kod odzyskiwania”",
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
                return [text("Na tym komputerze nie ma rozpoznawania mowy, więc nasłuch nie miałby czego zapisać.")]

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
    def _mail(self, identity, message, plain, case):
        s = self.s
        if not re.search(r"\b(poczt\w*|mail\w*|maile|wiadomosc\w*|skrzynk\w*|outlook\w*|thunderbird\w*)\b", plain):
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
            return [text(head + "\n\n" + body),
                    buttons((f"Dodaj do sprawy{' „' + case + '”' if case else ''}", f"dodaj mail {index} do sprawy"))]
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
        return [text("\n".join(lines)), buttons(*[(f"Pokaż {n}", f"mail {n}") for n in range(1, len(listed) + 1)])]

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
                 "offsite-backup": "wysłał kopię poza kancelarię", "restore": "odtworzył sejf z kopii",
                 "enroll-recovery": "utworzył kod odzyskiwania", "revoke-device": "cofnął dostęp urządzenia",
                 "settings": "zmienił ustawienia", "rotate-key": "wymienił klucz sejfu", "migrate": "przeniósł sejf do nowego formatu",
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
