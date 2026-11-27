"""Read the notary's mail from the program already on this computer. Read-only, local.

Nothing is copied or sent anywhere: a message enters the vault only when the notary adds it
to a case, and reaches the model only as part of a case document.

  Thunderbird  reads the profile's Inbox files (mbox) directly; Thunderbird may stay open.
  Outlook      asks classic Outlook through its automation interface (Windows only).
  folder       a directory of .eml files, for any other mail program that can export.
"""
import email
import email.policy
import os
import re
from dataclasses import dataclass
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

TAIL = 12 * 1024 * 1024      # newest messages sit at the end of an mbox; never read gigabytes
MAX_TEXT = 200_000


class MailError(Exception):
    """Fixed message, safe to show."""


@dataclass
class Message:
    sender: str
    address: str
    subject: str
    when: float
    text: str
    attachments: list
    raw: bytes | None = None       # original .eml bytes when the source has them

    def summary(self) -> dict:
        return {"sender": self.sender or self.address, "subject": self.subject or "(bez tematu)", "when": self.when}


def _body(message) -> tuple[str, list]:
    attachments = [part.get_filename() for part in message.walk() if part.get_filename()]
    part = message.get_body(preferencelist=("plain", "html")) if hasattr(message, "get_body") else None
    try:
        content = part.get_content() if part is not None else ""
    except (LookupError, ValueError, KeyError):
        content = ""
    if part is not None and part.get_content_type() == "text/html":
        content = re.sub(r"(?is)<(script|style).*?</\1>", " ", content)
        content = re.sub(r"(?s)<[^>]+>", " ", content)
    return re.sub(r"[ \t]+", " ", str(content)).strip()[:MAX_TEXT], attachments


def parse(raw: bytes) -> Message | None:
    try:
        message = email.message_from_bytes(raw, policy=email.policy.default)
        if message.get("From") is None and message.get("Subject") is None and message.get("Date") is None:
            return None        # not a mail message at all
        name, address = parseaddr(str(message.get("From", "")))
        try:
            when = parsedate_to_datetime(str(message.get("Date"))).timestamp()
        except (TypeError, ValueError, IndexError):
            when = 0.0
        text, attachments = _body(message)
        return Message(name, address, str(message.get("Subject", "")).strip(), when, text, attachments, raw)
    except Exception:
        return None            # one malformed message must not hide the rest


def _newest(messages, limit):
    return sorted((m for m in messages if m is not None), key=lambda m: m.when, reverse=True)[:limit]


class Thunderbird:
    name = "Thunderbird"

    def __init__(self, profiles: Path | None = None):
        self._profiles = Path(profiles) if profiles else self.default_location()
        self.location = str(profiles) if profiles else None      # stored only when it is not the usual place

    @staticmethod
    def default_location() -> Path:
        if os.name == "nt":
            return Path(os.environ.get("APPDATA", "")) / "Thunderbird" / "Profiles"
        return Path.home() / ".thunderbird"

    def _inboxes(self) -> list[Path]:
        if not self._profiles.is_dir():
            return []
        found = []
        for store in ("ImapMail", "Mail"):
            found += [p for p in self._profiles.glob(f"*/{store}/*/I[Nn][Bb][Oo][Xx]") if p.is_file()]
        return found

    def available(self) -> bool:
        return bool(self._inboxes())

    def latest(self, limit: int = 10) -> list[Message]:
        messages = []
        for inbox in self._inboxes():
            try:
                size = inbox.stat().st_size
                with inbox.open("rb") as file:      # plain read: no lock, Thunderbird keeps working
                    file.seek(max(0, size - TAIL))
                    data = file.read()
            except OSError:
                continue
            chunks = re.split(rb"(?m)^From .*\r?\n", data)
            if size > TAIL:
                chunks = chunks[1:]                 # the first piece starts mid-message
            for chunk in chunks[-(limit * 3):]:
                if chunk.strip():
                    # X-Mozilla-Status 0008 marks a message deleted but not yet compacted.
                    status = re.search(rb"(?m)^X-Mozilla-Status: ([0-9a-fA-F]{4})", chunk[:4096])
                    if status and int(status.group(1), 16) & 0x0008:
                        continue
                    messages.append(parse(chunk))
        return _newest(messages, limit)


class Outlook:
    """Classic Outlook for Windows. The new Outlook app has no automation interface: use `folder`."""
    name = "Outlook"

    def __init__(self, dispatch=None):
        self._dispatch = dispatch

    def _application(self):
        if self._dispatch is not None:
            return self._dispatch("Outlook.Application")
        if os.name != "nt":
            raise MailError("Outlook jest dostępny tylko na Windows.")
        try:
            import win32com.client

            return win32com.client.Dispatch("Outlook.Application")
        except Exception:
            raise MailError("Nie udało się połączyć z Outlookiem. Działa to z klasycznym Outlookiem; "
                            "w nowym Outlooku zapisz wiadomości do folderu i napisz „połącz pocztę folder …”.") from None

    def available(self) -> bool:
        if self._dispatch is None and os.name != "nt":
            return False
        try:
            self._application().GetNamespace("MAPI")
            return True
        except Exception:
            return False

    def latest(self, limit: int = 10) -> list[Message]:
        try:
            inbox = self._application().GetNamespace("MAPI").GetDefaultFolder(6)      # 6 = Inbox
            items = inbox.Items
            items.Sort("[ReceivedTime]", True)
            messages = []
            for index in range(1, min(int(items.Count), limit * 2) + 1):
                item = items.Item(index)
                if getattr(item, "Class", 43) != 43:       # 43 = a mail item; skip meeting requests etc.
                    continue
                received = getattr(item, "ReceivedTime", None)
                messages.append(Message(
                    str(getattr(item, "SenderName", "") or ""), str(getattr(item, "SenderEmailAddress", "") or ""),
                    str(getattr(item, "Subject", "") or ""),
                    received.timestamp() if hasattr(received, "timestamp") else 0.0,
                    str(getattr(item, "Body", "") or "")[:MAX_TEXT],
                    [str(a.FileName) for a in getattr(item, "Attachments", [])],
                ))
            return _newest(messages, limit)
        except MailError:
            raise
        except Exception:
            raise MailError("Outlook nie odpowiedział. Sprawdź, czy jest uruchomiony, i spróbuj ponownie.") from None


class Folder:
    name = "folder"

    def __init__(self, path):
        self._path = Path(path)

    def available(self) -> bool:
        return self._path.is_dir()

    def latest(self, limit: int = 10) -> list[Message]:
        if not self.available():
            raise MailError("Folder z wiadomościami jest niedostępny.")
        files = sorted(self._path.glob("*.eml"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit * 3]
        messages = []
        for path in files:
            try:
                if path.stat().st_size <= 25 * 1024 * 1024:
                    message = parse(path.read_bytes())
                    if message is not None and not message.when:
                        message.when = path.stat().st_mtime
                    messages.append(message)
            except OSError:
                continue
        return _newest(messages, limit)


def detect() -> list:
    """Mail programs found on this computer, most specific first."""
    return [source for source in (Thunderbird(), Outlook()) if source.available()]


def open_source(kind: str | None, path: str | None = None):
    if kind == "thunderbird":
        return Thunderbird(Path(path) if path else None)
    if kind == "outlook":
        return Outlook()
    if kind == "folder" and path:
        return Folder(path)
    return None


def as_document(message: Message) -> tuple[str, bytes]:
    """A message as a case document: the original .eml when we have it, otherwise readable text."""
    stem = re.sub(r"[^\w -]", "", message.subject)[:60].strip() or "wiadomosc"
    if message.raw is not None:
        return f"mail - {stem}.eml", message.raw
    lines = [f"Od: {message.sender} <{message.address}>", f"Temat: {message.subject}"]
    if message.attachments:
        lines.append("Załączniki (niezapisane): " + ", ".join(message.attachments))
    return f"mail - {stem}.txt", ("\n".join(lines) + "\n\n" + message.text).encode()
