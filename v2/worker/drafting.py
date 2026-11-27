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


class Drafts:
    def __init__(self, vault: Vault, inference: Inference, connect: ConnectSession):
        self._vault, self._inference, self._connect = vault, inference, connect
        self._proposals: dict[str, Proposal] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ context
    def _context(self, case: str, actor: str) -> tuple[str, list[dict], list[str]]:
        sources, skipped, parts, used = [], [], [], 0
        for item in self._vault.summaries(cases={case}):
            lowered = item["name"].lower()
            if not lowered.endswith((".txt", ".docx")):
                skipped.append(item["name"])
                continue
            version, name, data = self._vault.get(item["id"], item["version"], actor=actor)
            try:
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
            raise DraftError("W tej sprawie nie ma dokumentów tekstowych (TXT lub DOCX) do odczytania.")
        return "\n\n".join(parts), sources, skipped

    # ------------------------------------------------------------ operations
    def ask(self, case: str, question: str, actor: str, names=()) -> dict:
        context, sources, skipped = self._context(case, actor)
        answer = self._inference.ask(
            purpose="chat", system=SYSTEM_CHAT, names=names, max_tokens=2048,
            text=f"{context}\n\n=== PYTANIE NOTARIUSZA ===\n{question}",
        )
        return {"answer": answer.text, "sources": sources, "skipped": skipped,
                "unknown_placeholders": list(answer.unknown_placeholders)}

    def propose(self, case: str, instruction: str, actor: str, names=()) -> Proposal:
        context, sources, skipped = self._context(case, actor)
        answer = self._inference.ask(
            purpose="draft", system=SYSTEM_DRAFT, names=names, max_tokens=16000,
            text=f"{context}\n\n=== POLECENIE NOTARIUSZA ===\n{instruction}",
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
            answer.input_tokens, answer.output_tokens,
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
