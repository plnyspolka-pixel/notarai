"""Case documents -> model draft -> human approval -> DOCX revision in the vault.

A proposal lives in memory only. Nothing is written until the notary approves the
exact text; the approval is bound to its SHA-256 through the Connect SDK.
"""
import secrets
import threading
import time
from dataclasses import dataclass, field
from uuid import UUID

from .connect import State
from .connect_sdk import ConnectSession, RevisionTarget, WriteDocx
from .docx_adapter import DOCX_APP
from .docx_writer import canonical, digest, extract
from .inference import Inference
from .vault import Vault

PROPOSAL_TTL = 30 * 60
MAX_PROPOSALS = 20
MAX_CONTEXT_CHARS = 400_000

SYSTEM_DRAFT = (
    "Jesteś asystentem polskiej kancelarii notarialnej. Na podstawie dokumentów sprawy i polecenia "
    "notariusza przygotuj projekt dokumentu. Zasady:\n"
    "1. Pisz wyłącznie treść dokumentu, bez komentarzy i wstępów. Każdy akapit w osobnym wierszu. "
    "Tytuł poprzedź znakami '# '.\n"
    "2. Znaczniki w nawiasach kwadratowych, np. [OSOBA_1] albo [PESEL_1], zastępują dane osobowe. "
    "Przepisuj je dokładnie tak, jak je widzisz, i nie twórz nowych.\n"
    "3. Nie zmyślaj faktów, kwot, dat ani numerów. Gdy czegoś brakuje, wpisz [DO UZUPEŁNIENIA: czego brakuje].\n"
    "4. Nie obliczaj taksy notarialnej ani podatków; oblicza je program.\n"
    "5. Projekt jest propozycją do sprawdzenia przez notariusza."
)
SYSTEM_GENERAL = (
    "Jesteś asystentem polskiej kancelarii notarialnej i rozmawiasz z notariuszem albo pracownikiem kancelarii. "
    "Odpowiadaj po polsku, rzeczowo i krótko. W sprawach prawa podawaj podstawę prawną, gdy ją znasz, i mów wprost, "
    "gdy czegoś nie wiesz albo przepis mógł się zmienić. Nie obliczaj taksy notarialnej: oblicza ją program "
    "(wystarczy napisać „taksa”). Znaczniki w nawiasach kwadratowych zastępują dane osobowe: przepisuj je bez zmian."
)
NEXT_STEPS = (
    " Na samym końcu dodaj jedną osobną linię zaczynającą się od „DALEJ:” z jednym do trzech następnych kroków, "
    "które notariusz może zlecić temu programowi, jako krótkie polecenia po polsku (np. „sprawdź KW”, „sprawdź strony "
    "w KRZ”, „przygotuj projekt umowy”, „termin jutro 10:00 …”), oddzielone znakiem |. Proponuj tylko kroki, które "
    "naprawdę wynikają z sytuacji."
)
SYSTEM_CHAT = (
    "Jesteś asystentem polskiej kancelarii notarialnej. Odpowiadaj zwięźle, wyłącznie na podstawie "
    "dokumentów sprawy podanych niżej. Jeśli odpowiedzi w nich nie ma, powiedz to wprost. "
    "Znaczniki w nawiasach kwadratowych zastępują dane osobowe: przepisuj je bez zmian."
)


class DraftError(Exception):
    """Fixed message, safe to show."""


@dataclass
class Proposal:
    id: str
    case: str
    paragraphs: tuple[str, ...]
    sources: list[dict]
    skipped: list[str]
    actor: str
    expires: float
    unknown_placeholders: tuple[str, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    instruction: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def public(self) -> dict:
        return {
            "id": self.id, "case": self.case, "paragraphs": list(self.paragraphs),
            "sources": self.sources, "skipped": self.skipped,
            "unknown_placeholders": list(self.unknown_placeholders),
            "gaps": sum(p.count("[DO UZUPEŁNIENIA") for p in self.paragraphs),
            "tokens": {"input": self.input_tokens, "output": self.output_tokens},
            "expires_in": max(0, int(self.expires - time.monotonic())),
        }


READABLE = (".txt", ".docx", ".eml", ".pdf")


def pdf_text(data: bytes) -> str:
    """Text layer of a PDF (scans without text yield nothing and are reported as unreadable)."""
    import io

    from pypdf import PdfReader

    text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(data)).pages[:200]).strip()
    if not text:
        raise ValueError("no text layer")
    return text


class Drafts:
    def __init__(self, vault: Vault, inference: Inference, connect: ConnectSession, rules=None, style=None,
                 learning=None):
        # `inference` may be a callable so the worker can swap it when settings change.
        self._vault, self._source, self._connect = vault, inference, connect
        self._rules, self._style = rules, style
        self._proposals: dict[str, Proposal] = {}
        self._lock = threading.Lock()
        self._learning = learning

    @property
    def _inference(self) -> Inference:
        return self._source() if callable(self._source) else self._source

    # ------------------------------------------------------------ context
    def _context(self, case: str, actor: str, only: str | None = None) -> tuple[str, list[dict], list[str]]:
        sources, skipped, parts, used = [], [], [], 0
        for item in self._vault.summaries(cases={case}):
            if only is not None and item["id"] != only:
                continue
            lowered = item["name"].lower()
            if not lowered.endswith(READABLE):
                skipped.append(item["name"])
                continue
            version, name, data = self._vault.get(item["id"], item["version"], actor=actor)
            try:
                if lowered.endswith(".eml"):
                    from .mail import parse

                    mail = parse(data)
                    if mail is None:
                        raise ValueError("unreadable message")
                    text = f"Wiadomość e-mail od {mail.sender} <{mail.address}>, temat: {mail.subject}\n{mail.text}"
                elif lowered.endswith(".pdf"):
                    text = pdf_text(data)
                else:
                    text = data.decode("utf-8") if lowered.endswith(".txt") else "\n".join(extract(data))
            except (UnicodeDecodeError, ValueError, KeyError, OSError):
                skipped.append(name)
                continue
            except Exception:      # a malformed DOCX must not take the request down
                skipped.append(name)
                continue
            if used + len(text) > MAX_CONTEXT_CHARS:
                skipped.append(name)
                continue
            used += len(text)
            sources.append({"id": item["id"], "version": version, "name": name})
            parts.append(f"=== DOKUMENT {len(sources)} ===\n{text}")
        if not parts:
            raise DraftError("Tego pliku nie umiem odczytać (czytam DOCX, PDF z tekstem, TXT i e-mail)." if only else
                             "W tej sprawie nie ma dokumentów tekstowych (DOCX, PDF, TXT lub e-mail) do odczytania.")
        return "\n\n".join(parts), sources, skipped

    def case_text(self, case: str, actor: str) -> str:
        """All readable text of a case (for finding land register numbers and PESELs), or ""."""
        try:
            return self._context(case, actor)[0]
        except DraftError:
            return ""

    # ------------------------------------------------------------ operations
    def _names(self, case: str, names) -> list[str]:
        """People remembered for the case plus any named in this request."""
        return list(dict.fromkeys([*self._vault.parties(case), *names]))

    def ask(self, case: str, question: str, actor: str, names=(), document: str | None = None) -> dict:
        names = self._names(case, names)
        context, sources, skipped = self._context(case, actor, only=document)
        answer = self._inference.ask(
            purpose="chat", system=SYSTEM_CHAT + NEXT_STEPS, names=names, max_tokens=2048,
            text=f"{context}{self._learned()}\n\n=== PYTANIE NOTARIUSZA ===\n{question}",
        )
        return {"answer": answer.text, "sources": sources, "skipped": skipped,
                "unknown_placeholders": list(answer.unknown_placeholders)}

    def _learned(self, purpose: str = "wiedza") -> str:
        return self._learning.guidance(purpose) if self._learning is not None else ""

    def general(self, question: str, names=(), mail: bool = False) -> dict:
        """A question with no case chosen: the assistant answers from general knowledge, reading no documents."""
        answer = self._inference.ask(purpose="chat", system=SYSTEM_GENERAL + ("" if mail else NEXT_STEPS),
                                     names=list(names), max_tokens=2048,
                                     text=question + self._learned("mail" if mail else "wiedza"))
        return {"answer": answer.text, "unknown_placeholders": list(answer.unknown_placeholders)}

    def propose(self, case: str, instruction: str, actor: str, names=()) -> Proposal:
        names = self._names(case, names)
        context, sources, skipped = self._context(case, actor)
        guidance = ""
        if self._style is not None:
            guidance += self._style.guidance(instruction)
        if self._learning is not None:
            guidance += self._learning.guidance("akt")
        if self._rules is not None:
            required = self._rules.required_wording(instruction)
            if required:
                guidance += ("\n\n=== WYMAGANE SFORMUŁOWANIA (zasady kancelarii, sprawdzane przed zapisem) ===\n"
                             + "\n".join(f"- {wording}" for wording in required))
        answer = self._inference.ask(
            purpose="draft", system=SYSTEM_DRAFT, names=names, max_tokens=16000,
            text=f"{context}{guidance}\n\n=== POLECENIE NOTARIUSZA ===\n{instruction}",
        )
        if answer.stop_reason == "max_tokens":
            raise DraftError("Projekt nie zmieścił się w jednej odpowiedzi. Zawęź polecenie.")
        try:
            paragraphs = canonical(answer.text)
        except ValueError:
            raise DraftError("Model nie zwrócił tekstu projektu.") from None
        proposal = Proposal(
            secrets.token_urlsafe(16), case, paragraphs, sources, skipped, actor,
            time.monotonic() + PROPOSAL_TTL, answer.unknown_placeholders,
            answer.input_tokens, answer.output_tokens, instruction=instruction,
        )
        with self._lock:
            now = time.monotonic()
            self._proposals = {k: v for k, v in self._proposals.items() if v.expires > now}
            while len(self._proposals) >= MAX_PROPOSALS:
                self._proposals.pop(next(iter(self._proposals)))
            self._proposals[proposal.id] = proposal
        return proposal

    def get(self, proposal_id: str, actor: str) -> Proposal:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.expires <= time.monotonic() or proposal.actor != actor:
            raise DraftError("Projekt wygasł albo nie istnieje.")
        return proposal

    def discard(self, proposal_id: str, actor: str) -> None:
        self.get(proposal_id, actor)
        with self._lock:
            self._proposals.pop(proposal_id, None)

    def approve(self, proposal_id: str, actor: str, name: str, *, paragraphs=None,
                base: dict | None = None, template: dict | None = None) -> dict:
        """Write the approved text. `paragraphs` carries the notary's own edits, if any."""
        proposal = self.get(proposal_id, actor)
        if not proposal.lock.acquire(blocking=False):
            raise DraftError("Ten projekt jest właśnie zapisywany.")
        try:
            try:
                text = canonical(paragraphs if paragraphs is not None else proposal.paragraphs)
                request = WriteDocx(
                    app=DOCX_APP, name=name, case=proposal.case, content_sha256=digest(text),
                    base=_target(base), template=_target(template),
                )
            except (ValueError, TypeError):
                raise DraftError("Nazwa pliku albo treść projektu jest niepoprawna.") from None
            if self._rules is not None:
                from .rules import RuleViolation

                try:
                    self._rules.check_document(name, "\n".join(text), proposal.instruction)
                except RuleViolation as violation:
                    raise DraftError(str(violation)) from None
            for target in (request.base, request.template):
                if target is not None:
                    try:
                        if self._vault.case_of(str(target.document_id)) != proposal.case:
                            raise KeyError
                    except KeyError:
                        raise DraftError("Wskazany dokument nie należy do tej sprawy.") from None
            result = self._connect.execute(request, self._connect.approve(request), text, actor=actor)
            if result.state is State.VERIFIED:
                with self._lock:
                    self._proposals.pop(proposal_id, None)
                return {"id": str(result.data.target.document_id), "version": result.data.target.version,
                        "name": name, "state": "verified"}
            if result.state is State.UNAVAILABLE:
                raise DraftError("Zapis DOCX nie jest dostępny na tym stanowisku.")
            # Never retried automatically: the notary checks the document list first.
            raise DraftError("Nie udało się potwierdzić zapisu. Sprawdź listę dokumentów, zanim spróbujesz ponownie.")
        finally:
            proposal.lock.release()


def _target(value: dict | None) -> RevisionTarget | None:
    if value is None:
        return None
    return RevisionTarget(document_id=UUID(str(value["id"])), version=value["version"])
