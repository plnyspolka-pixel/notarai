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
    entry_id: str | None = None    # Outlook's id of the item, to reach attachments and reply

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
                    entry_id=str(getattr(item, "EntryID", "") or "") or None,
                ))
            return _newest(messages, limit)
        except MailError:
            raise
        except Exception:
            raise MailError("Outlook nie odpowiedział. Sprawdź, czy jest uruchomiony, i spróbuj ponownie.") from None


    def attachment(self, entry_id: str, index: int) -> bytes:
        import tempfile

        try:
            item = self._application().GetNamespace("MAPI").GetItemFromID(entry_id)
            with tempfile.TemporaryDirectory() as scratch:
                path = Path(scratch) / "zalacznik"
                item.Attachments.Item(index + 1).SaveAsFile(str(path))
                return path.read_bytes()
        except Exception:
            raise MailError("Outlook nie oddał tego załącznika. Spróbuj ponownie.") from None

    def compose(self, to: str, subject: str, body: str, reply_to: Message | None = None) -> None:
        """Open a ready message in Outlook's own window. Sending stays with the notary (Wyślij in Outlook)."""
        try:
            application = self._application()
            if reply_to is not None and reply_to.entry_id:
                item = application.GetNamespace("MAPI").GetItemFromID(reply_to.entry_id).Reply()
                item.Body = body + "\n\n" + str(item.Body or "")
            else:
                item = application.CreateItem(0)          # 0 = a mail item
                item.To, item.Subject, item.Body = to, subject, body
            item.Display(False)
        except MailError:
            raise
        except Exception:
            raise MailError("Nie udało się otworzyć wiadomości w Outlooku.") from None


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


def attachment(message: Message, index: int, source=None) -> tuple[str, bytes]:
    """(file name, content) of one attachment, taken from the original message."""
    if not 0 <= index < len(message.attachments):
        raise MailError("Ta wiadomość nie ma takiego załącznika.")
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(message.attachments[index]))[:120] or "zalacznik"
    if message.raw is not None:
        parsed = email.message_from_bytes(message.raw, policy=email.policy.default)
        parts = [part for part in parsed.walk() if part.get_filename()]
        if index < len(parts):
            data = parts[index].get_payload(decode=True) or b""
            if len(data) > 20 * 2**20:
                raise MailError("Ten załącznik jest większy niż 20 MiB.")
            return name, data
    if message.entry_id and hasattr(source, "attachment"):
        return name, source.attachment(message.entry_id, index)
    raise MailError("Nie umiem odczytać tego załącznika z tej poczty.")


def thunderbird_program() -> Path | None:
    if os.name != "nt":
        return None
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
        candidate = Path(base) / "Mozilla Thunderbird" / "thunderbird.exe"
        if base and candidate.is_file():
            return candidate
    return None


def compose(source, to: str, subject: str, body: str, reply_to: Message | None = None, *, runner=None) -> str:
    """Open a ready message in the mail program for the notary to check and send. Returns where it opened."""
    if hasattr(source, "compose"):
        source.compose(to, subject, body, reply_to)
        return "Outlooku"
    import subprocess

    program = thunderbird_program() if isinstance(source, Thunderbird) else None
    quote = lambda value: "'" + value.replace("'", "’") + "'"
    if program is not None:
        (runner or subprocess.Popen)([str(program), "-compose",
                                      f"to={quote(to)},subject={quote(subject)},body={quote(body)}"])
        return "Thunderbirdzie"
    # Any other program: a ready .eml next to the mail folder, opened by the default mail program.
    from email.message import EmailMessage

    draft = EmailMessage()
    draft["To"], draft["Subject"] = to, subject
    draft["X-Unsent"] = "1"            # Outlook and Windows Mail open it as a message to send
    draft.set_content(body)
    folder = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NotarAI" / "do-wyslania"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ((re.sub(r"[^\w -]", "", subject)[:50].strip() or "wiadomosc") + ".eml")
    path.write_bytes(bytes(draft))
    if runner is None and hasattr(os, "startfile"):
        os.startfile(str(path))       # noqa: S606 - a file NotarAI just wrote
    elif runner is not None:
        runner([str(path)])
    return "domyślnym programie pocztowym"


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
