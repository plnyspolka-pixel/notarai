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

KINDS = {"poprawka": "Poprawki w aktach", "slownik": "Dyktowanie", "odpowiedz": "Odpowiedzi na maile",
         "wiedza": "Wiedza kancelarii", "korekta": "Korekty odpowiedzi"}
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


class Learning:
    def __init__(self, vault, enabled=lambda: True, clock=time.time):
        self._vault, self._enabled, self._clock = vault, enabled, clock

    @property
    def enabled(self) -> bool:
        return bool(self._enabled())

    # ------------------------------------------------------------ store
    def lessons(self, kind: str | None = None) -> list[dict]:
        found = [l for l in self._vault.lessons() if kind is None or l["kind"] == kind]
        return sorted(found, key=lambda l: l["created"])

    def confirmed(self, kind: str | None = None) -> list[dict]:
        return [l for l in self.lessons(kind) if l.get("status", "potwierdzona") == "potwierdzona"]

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
        """Lessons from the notary's edits of a draft: at most five per act, the clearest ones."""
        if not self.enabled:
            return []
        before, after = sentences(proposed), sentences(approved)
        learned = []
        matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal" or len(learned) >= 5:
                continue
            was = [anonymize(s, names) for s in before[i1:i2]]
            now = [anonymize(s, names) for s in after[j1:j2]]
            if tag == "replace" and len(was) == len(now):
                for old, new in zip(was, now):
                    if old != new and len(old) < 400 and len(new) < 400 \
                            and difflib.SequenceMatcher(a=old, b=new).ratio() > 0.35:
                        lesson = self._add("poprawka", f"Zamiast „{old}” piszę „{new}”.",
                                           {"was": old, "now": new, "act": kind}, "r:" + old)
                        if lesson:
                            learned.append(lesson)
            elif tag == "delete":
                for old in was:
                    if len(old) < 400:
                        lesson = self._add("poprawka", f"Nie dodaję zdania „{old}”.", {"was": old, "now": "", "act": kind},
                                           "d:" + old)
                        if lesson:
                            learned.append(lesson)
            elif tag == "insert":
                for new in now:
                    if len(new) < 400:
                        lesson = self._add("poprawka", f"Dodaję zdanie „{new}”" + (f" ({kind})." if kind else "."),
                                           {"was": "", "now": new, "act": kind}, "i:" + new)
                        if lesson:
                            learned.append(lesson)
        return learned[:5]

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
            lesson = self._add("slownik", f"Gdy słyszę „{wrong}”, piszę „{right}”.", {"heard": wrong, "say": right},
                               "s:" + wrong.lower())
            if lesson:
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
        lesson = self._add("odpowiedz", "Przykład odpowiedzi kancelarii: „" + example[:120] + ("…”" if len(example) > 120 else "”"),
                           {"example": example}, "o:" + example[:200])
        replies = self.lessons("odpowiedz")
        for old in replies[:-5]:                     # the five latest examples are enough
            self._vault.lesson_delete(old["id"])
        return [lesson] if lesson else []

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
        if purpose == "akt":
            edits = sorted(self.confirmed("poprawka"), key=lambda l: (-l.get("seen", 1), -l["created"]))[:25]
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
