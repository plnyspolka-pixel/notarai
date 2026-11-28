"""Learning mode: NotarAI learns from how the office works, visibly and under the notary's control.

Fronts (each lesson learned by watching is first proposed: "Nauczyłem się tego, potwierdzasz?", and used
only after a yes; lessons the notary states are used at once; all are listed and can be forgotten):
  akty       a draft compared with what the notary approved: replaced, removed and added sentences
  dyktowanie words the notary corrects after dictation; applied to the next dictations at once
  poczta     the notary's own replies, as examples of the office's tone for the next drafts
  wiedza     „zapamiętaj: …” and „to było źle: …”: knowledge and corrections used in every answer

Lessons are guidance for the assistant, never hard rules (those are the office rules, checked by
code). Names of the case parties, numbers and e-mail addresses are cut out before a lesson is kept,
and lessons live encrypted in the vault, like documents.
"""
import difflib
import re
import secrets
import time

KINDS = {"zasada": "Zasady stylu kancelarii", "poprawka": "Poprawki w aktach", "slownik": "Dyktowanie", "odpowiedz": "Odpowiedzi na maile",
         "wiedza": "Wiedza kancelarii", "korekta": "Korekty odpowiedzi", "komputer": "Praca na komputerze"}
MAX_LESSONS = 400
SENTENCE = re.compile(r"(?<=[.!?;:])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„(])")


def anonymize(text: str, names=()) -> str:
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", text)
    for name in sorted({n for n in names if n and len(n) > 2}, key=len, reverse=True):
        text = re.sub(re.escape(name), "[osoba]", text, flags=re.I)
        for part in name.split():
            if len(part) >= 4:            # Polish inflection: Anna -> Anny, Nowak -> Nowakowi
                stem = part[0].upper() + re.escape(part[1:-1].lower())
                text = re.sub(r"\b" + stem + r"\w*", "[osoba]", text)
            elif len(part) == 3:
                text = re.sub(r"\b" + re.escape(part) + r"\b", "[osoba]", text, flags=re.I)
    text = re.sub(r"\d", "#", text)
    return re.sub(r"\[osoba\](\s+\[osoba\])+", "[osoba]", " ".join(text.split()))


def sentences(paragraphs) -> list[str]:
    out = []
    for paragraph in paragraphs:
        out += [s.strip() for s in SENTENCE.split(str(paragraph)) if s.strip()]
    return out


SYSTEM_INSIGHT = (
    "Jesteś doświadczonym notariuszem i uczysz się stylu pracy kancelarii. Dostajesz poprawki, które notariusz "
    "naniósł na projekt (było -> jest). Sformułuj od jednej do trzech OGÓLNYCH zasad, które z nich wynikają i przydadzą "
    "się przy następnych aktach tego rodzaju: co kancelaria zawsze dodaje, czego nie pisze, jak formułuje pouczenia, "
    "oświadczenia, opisy nieruchomości. Każda zasada w osobnej linii, zaczynającej się od „- ”, jednym zdaniem. "
    "Pomiń literówki, wielkość liter, interpunkcję i dane tej konkretnej sprawy. Jeśli nie wynika z nich nic ogólnego, "
    "odpowiedz jednym słowem: BRAK."
)
SYSTEM_COMPUTER = (
    "Program NotarAI wykonywał na komputerze kancelarii polecenie notariusza (pliki, programy Windows, strony). "
    "Dostajesz przebieg: kroki, błędy i to, co w końcu zadziałało albo co odpowiedział notariusz. Sformułuj jedną albo "
    "dwie OGÓLNE wskazówki na przyszłość, które oszczędzą prób przy następnym podobnym zadaniu, np. „W RejNET pole "
    "Numer aktu jest na zakładce Repertorium; najpierw ją kliknij.” albo „Na stronie EKW przycisk Dalej działa dopiero "
    "po zaznaczeniu zgody.” Podaj program albo stronę, której dotyczy. Bez nazwisk, numerów i danych tej sprawy. Każda "
    "wskazówka w osobnej linii zaczynającej się od „- ”. Jeśli nic ogólnego z tego nie wynika, odpowiedz: BRAK."
)
SYSTEM_TONE = (
    "Opisz w jednym do trzech zdań styl, w jakim kancelaria notarialna odpowiada na e-maile, na podstawie jej "
    "odpowiedzi poniżej: zwrot grzecznościowy, długość, ton, jak podaje terminy i co zawsze dopisuje. Każde zdanie "
    "w osobnej linii od „- ”. Bez danych konkretnych osób."
)


def trivial(old: str, new: str) -> bool:
    """A correction not worth a lesson: capital letters, punctuation, spacing, a typo of a letter or two."""
    plain = lambda t: re.sub(r"[\W_]+", "", t.lower())
    if plain(old) == plain(new):
        return True
    a, b = plain(old), plain(new)
    return abs(len(a) - len(b)) <= 2 and difflib.SequenceMatcher(a=a, b=b).ratio() >= 0.9 and len(a) > 12


class Learning:
    def __init__(self, vault, enabled=lambda: True, clock=time.time, inference=None):
        self._vault, self._enabled, self._clock = vault, enabled, clock
        self._inference = inference or (lambda: None)

    def _insights(self, system: str, material: str, act: str, kind: str = "zasada",
                  status: str = "proponowana") -> list[dict]:
        """General rules the assistant draws from the notary's own work; proposed, never used before a yes."""
        inference = self._inference()
        if inference is None or not getattr(inference, "enabled", False):
            return []
        try:
            answer = inference.ask(purpose="insight", system=system, text=material[:20000], max_tokens=600)
        except Exception:
            return []
        learned = []
        for line in answer.text.splitlines():
            rule = line.strip().lstrip("-•* ").strip()
            if len(rule) < 15 or rule.upper().startswith("BRAK") or "[" in rule:
                continue
            lesson = self._add(kind, rule + (f" ({act})" if act and kind == "zasada" else ""), {"act": act}, "z:" + rule.lower(),
                               status=status)
            if lesson:
                learned.append(lesson)
        return learned[:3]

    @property
    def enabled(self) -> bool:
        return bool(self._enabled())

    # ------------------------------------------------------------ store
    def lessons(self, kind: str | None = None) -> list[dict]:
        found = [l for l in self._vault.lessons() if kind is None or l["kind"] == kind]
        return sorted(found, key=lambda l: l["created"])

    def confirmed(self, kind: str | None = None) -> list[dict]:
        return [l for l in self.lessons(kind) if l.get("status", "potwierdzona") == "potwierdzona"]

    def lessons_with(self, status: str) -> list[dict]:
        return [l for l in self.lessons() if l.get("status") == status]

    def pending(self) -> list[dict]:
        return [l for l in self.lessons() if l.get("status") == "proponowana"]

    def decide(self, ident: str, accept: bool, actor: str = "local-admin") -> dict | None:
        lesson = next((l for l in self.lessons() if l["id"] == ident), None)
        if lesson is None:
            return None
        if not accept:
            self._vault.lesson_delete(ident, actor=actor)
            return {**lesson, "status": "odrzucona"}
        lesson["status"] = "potwierdzona"
        self._vault.lesson_put(ident, {k: v for k, v in lesson.items() if k != "id"})
        return lesson

    def _add(self, kind: str, text: str, data: dict, key: str, status: str = "proponowana") -> dict | None:
        existing = [l for l in self.lessons(kind) if l.get("key") == key]
        if existing:
            lesson = existing[0]
            lesson["seen"] = lesson.get("seen", 1) + 1
            self._vault.lesson_put(lesson["id"], {k: v for k, v in lesson.items() if k != "id"})
            return None                     # known already: stronger, not new
        everything = self.lessons()
        if len(everything) >= MAX_LESSONS:
            self._vault.lesson_delete(everything[0]["id"])
        lesson = {"kind": kind, "text": text, "data": data, "key": key, "created": self._clock(), "seen": 1,
                  "status": status}
        ident = secrets.token_hex(6)
        self._vault.lesson_put(ident, lesson)
        return {"id": ident, **lesson}

    def forget(self, ident: str, actor: str = "local-admin") -> bool:
        return self._vault.lesson_delete(ident, actor=actor)

    # ------------------------------------------------------------ fronts
    def from_draft(self, proposed, approved, names=(), kind: str = "") -> list[dict]:
        """What the notary's edits of a draft teach: general rules worked out by the assistant (proposed for a
        yes). The exact edits are kept quietly as material; capital letters and typos are not lessons."""
        if not self.enabled:
            return []
        edits = self._draft_edits(proposed, approved, names, kind)
        if not edits:
            return []
        material = "\n".join(f"BYŁO: {e['was'] or '(nic)'}\nJEST: {e['now'] or '(usunięte)'}" for e in edits)
        insights = self._insights(SYSTEM_INSIGHT, f"Rodzaj aktu: {kind or 'nieznany'}\n\n{material}", kind)
        if insights:
            for e in edits:                     # the material behind the rules: used once the rules are confirmed
                self._add("poprawka", e["text"], e, e["key"], status="material")
            return insights
        return [lesson for e in edits if (lesson := self._add("poprawka", e["text"], e, e["key"]))][:5]

    def _draft_edits(self, proposed, approved, names=(), kind: str = "") -> list[dict]:
        before, after = sentences(proposed), sentences(approved)
        learned: list[dict] = []
        matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal" or len(learned) >= 12:
                continue
            was = [anonymize(s, names) for s in before[i1:i2]]
            now = [anonymize(s, names) for s in after[j1:j2]]
            if tag == "replace" and len(was) == len(now):
                for old, new in zip(was, now):
                    if old != new and len(old) < 400 and len(new) < 400 and not trivial(old, new) \
                            and difflib.SequenceMatcher(a=old, b=new).ratio() > 0.35:
                        learned.append({"text": f"Zamiast „{old}” piszę „{new}”.", "was": old, "now": new, "act": kind,
                                        "key": "r:" + old})
            elif tag == "delete":
                for old in was:
                    if len(old) < 400:
                        learned.append({"text": f"Nie dodaję zdania „{old}”.", "was": old, "now": "", "act": kind, "key": "d:" + old})
            elif tag == "insert":
                for new in now:
                    if len(new) < 400:
                        learned.append({"text": f"Dodaję zdanie „{new}”" + (f" ({kind})." if kind else "."),
                                        "was": "", "now": new, "act": kind, "key": "i:" + new})
        return learned

    def from_dictation(self, heard: str, final: str) -> list[dict]:
        """Words corrected after dictation (1-3 words each side), kept as a dictation dictionary."""
        if not self.enabled or not heard or not final:
            return []
        a, b = heard.split(), final.split()
        learned = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
            if tag != "replace" or not (1 <= i2 - i1 <= 3 and 1 <= j2 - j1 <= 3):
                continue
            wrong, right = " ".join(a[i1:i2]).strip(".,;:!?"), " ".join(b[j1:j2]).strip(".,;:!?")
            if any(c.isdigit() for c in wrong + right) or wrong == right:
                continue
            if difflib.SequenceMatcher(a=wrong.lower(), b=right.lower()).ratio() < 0.4:
                continue                    # a different word entirely: an edit, not a misheard one
            quiet = wrong.lower() == right.lower()       # only capital letters: just do it, no lesson to confirm
            lesson = self._add("slownik", f"Gdy słyszę „{wrong}”, piszę „{right}”.", {"heard": wrong, "say": right},
                               "s:" + wrong.lower(), status="potwierdzona" if quiet else "proponowana")
            if lesson and not quiet:
                learned.append(lesson)
        return learned[:5]

    def apply_dictation(self, text: str) -> str:
        if not self.enabled:
            return text
        for lesson in self.confirmed("slownik"):
            heard, say = lesson["data"]["heard"], lesson["data"]["say"]
            text = re.sub(r"(?<!\w)" + re.escape(heard) + r"(?!\w)", say, text, flags=re.I)
        return text

    def from_reply(self, body: str, names=()) -> list[dict]:
        if not self.enabled or len(body.strip()) < 20:
            return []
        example = anonymize(body.strip(), names)[:800]
        self._add("odpowiedz", "Przykład odpowiedzi kancelarii: „" + example[:120] + ("…”" if len(example) > 120 else "”"),
                  {"example": example}, "o:" + example[:200], status="potwierdzona")    # her own words: no question
        replies = self.lessons("odpowiedz")
        for old in replies[:-5]:                     # the five latest examples are enough
            self._vault.lesson_delete(old["id"])
        if len(replies) >= 3 and len(replies) % 3 == 0:  # every few replies: what is the office's style?
            examples = "\n---\n".join(l["data"]["example"] for l in self.lessons("odpowiedz"))
            return self._insights(SYSTEM_TONE, examples, "", kind="zasada")
        return []

    def from_agent(self, material: str, *, notary_answered: bool) -> list[dict]:
        """What the computer agent learned from one run. From the notary's own answer the lesson counts at once
        (the notary said it); drawn by the program from its own tries it is proposed („potwierdzasz?”)."""
        if not self.enabled:
            return []
        return self._insights(SYSTEM_COMPUTER, material, "", kind="komputer",
                              status="potwierdzona" if notary_answered else "proponowana")

    def computer_guidance(self) -> str:
        """Confirmed lessons about this computer's programs and pages, for the agent's instructions."""
        if not self.enabled:
            return ""
        lessons = [l["text"] for l in self.confirmed("komputer")][-40:] + [l["text"] for l in self.confirmed("wiedza")][-15:]
        return "\n".join(f"- {t}" for t in lessons)

    def remember(self, text: str, kind: str = "wiedza") -> dict | None:
        text = " ".join(text.split())[:500]
        if not text:
            return None
        return self._add(kind, text, {}, kind[0] + ":" + text.lower(), status="potwierdzona")   # said by the notary

    # ------------------------------------------------------------ use
    def guidance(self, purpose: str) -> str:
        """Text added to the assistant's instructions; empty when off or nothing was learned."""
        if not self.enabled:
            return ""
        parts = []
        knowledge = [l["text"] for l in self.confirmed("wiedza")][-30:] + [l["text"] for l in self.confirmed("korekta")][-20:]
        if knowledge:
            parts.append("=== WIEDZA I KOREKTY KANCELARII (od notariusza) ===\n" + "\n".join(f"- {k}" for k in knowledge))
        rules = [l["text"] for l in self.confirmed("zasada")]
        if rules:
            parts.append("=== ZASADY STYLU KANCELARII (wyciągnięte z pracy notariusza, potwierdzone) ===\n"
                         + "\n".join(f"- {r}" for r in rules[-30:]))
        if purpose == "akt":
            confirmed = self.confirmed("poprawka") + (self.lessons_with("material") if rules else [])
            edits = sorted(confirmed, key=lambda l: (-l.get("seen", 1), -l["created"]))[:25]
            if edits:
                parts.append("=== PREFERENCJE KANCELARII Z POPRAWEK NOTARIUSZA ([osoba] i # to dane do wstawienia) ===\n"
                             + "\n".join(f"- {l['text']}" for l in edits))
        if purpose == "mail":
            examples = [l["data"]["example"] for l in self.confirmed("odpowiedz")]
            if examples:
                parts.append("=== PRZYKŁADY ODPOWIEDZI KANCELARII (ton i forma) ===\n" + "\n---\n".join(examples))
        return ("\n\n" + "\n\n".join(parts)) if parts else ""

    def summary(self) -> dict:
        counts = {kind: 0 for kind in KINDS}
        for lesson in self.lessons():
            counts[lesson["kind"]] = counts.get(lesson["kind"], 0) + 1
        return {"enabled": self.enabled, "counts": counts, "total": sum(counts.values()), "pending": len(self.pending())}
