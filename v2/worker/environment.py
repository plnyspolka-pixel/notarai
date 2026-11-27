"""What is on this computer: the first screen of a new installation.

Mail programs, a word processor, browsers, programs used in notarial offices (registers, qualified
signatures, tax forms) and folders that hold many acts. Read only: nothing is changed, nothing is
sent anywhere; the result stays on this computer and is shown in the chat with a "connect" button
for each thing found.
"""
import os
import sys
import time
from pathlib import Path

# (fragment of the program name in lower case, shown name, kind, what NotarAI does with it)
KNOWN = [
    ("rejnet", "RejNET", "kancelaryjny",
     "repertorium i rejestry: pokaż raz wpis, potem NotarAI wpisuje dane sam"),
    ("notariusz", "Notariusz", "kancelaryjny", "program kancelaryjny: pokaż raz czynność, potem NotarAI robi ją sam"),
    ("repertorium", "Repertorium", "kancelaryjny", "repertorium: wpisy z danych aktu"),
    ("kancelaria", "Program kancelarii", "kancelaryjny", "pokaż raz czynność, potem NotarAI robi ją sam"),
    ("szafir", "Szafir (KIR)", "podpis", "podpis kwalifikowany: NotarAI przygotuje dokument, podpisujesz Ty"),
    ("procertum", "proCertum", "podpis", "podpis kwalifikowany: NotarAI przygotuje dokument, podpisujesz Ty"),
    ("certum", "Certum", "podpis", "podpis kwalifikowany: NotarAI przygotuje dokument, podpisujesz Ty"),
    ("sigillum", "Sigillum", "podpis", "podpis kwalifikowany: NotarAI przygotuje dokument, podpisujesz Ty"),
    ("cencert", "CenCert", "podpis", "podpis kwalifikowany: NotarAI przygotuje dokument, podpisujesz Ty"),
    ("eurocert", "EuroCert", "podpis", "podpis kwalifikowany: NotarAI przygotuje dokument, podpisujesz Ty"),
    ("e-deklaracje", "e-Deklaracje", "urzędowy", "deklaracje PCC-3: NotarAI wypełnia, wysyłasz po zatwierdzeniu"),
    ("klient jpk", "Klient JPK", "urzędowy", "pliki JPK"),
    ("platnik", "Płatnik", "urzędowy", "ZUS: pokaż raz, potem NotarAI wypełnia"),
    ("microsoft office", "Microsoft Office", "edytor", "akty otwierane i poprawiane w Wordzie, zapis wraca do sejfu"),
    ("microsoft 365", "Microsoft 365", "edytor", "akty otwierane i poprawiane w Wordzie, zapis wraca do sejfu"),
    ("libreoffice", "LibreOffice", "edytor", "akty otwierane i poprawiane w LibreOffice, zapis wraca do sejfu"),
    ("google chrome", "Google Chrome", "przegladarka", "strony urzędowe: EKW, KRZ, e-Urząd"),
    ("mozilla firefox", "Firefox", "przegladarka", "strony urzędowe: EKW, KRZ, e-Urząd"),
    ("microsoft edge", "Microsoft Edge", "przegladarka", "okno NotarAI i strony urzędowe"),
]
ACT_SUFFIXES = (".docx", ".doc", ".odt", ".rtf")


def installed_programs() -> list[str]:
    """Names from the Windows list of installed programs (current user and the whole computer)."""
    if sys.platform != "win32":
        return []
    import winreg

    names = set()
    path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    for root, view in ((winreg.HKEY_CURRENT_USER, 0), (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
                       (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY)):
        try:
            with winreg.OpenKey(root, path, 0, winreg.KEY_READ | view) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        with winreg.OpenKey(key, winreg.EnumKey(key, index)) as entry:
                            names.add(str(winreg.QueryValueEx(entry, "DisplayName")[0]))
                    except OSError:
                        continue
        except OSError:
            continue
    return sorted(names)


def default_roots() -> list[Path]:
    home = Path.home()
    roots = [home / "Documents", home / "Desktop", home / "OneDrive" / "Documents"]
    if sys.platform == "win32":
        roots += [Path(f"{letter}:\\") for letter in "DEFGH" if Path(f"{letter}:\\").exists()]
    return [r for r in roots if r.is_dir()]


def act_folders(roots, *, seconds: float = 8.0, depth: int = 4, clock=time.monotonic) -> list[dict]:
    """Folders with the most acts (DOCX/DOC/ODT/RTF directly inside), largest first. Bounded in time."""
    deadline = clock() + seconds
    found: dict[str, int] = {}
    for root in roots:
        root = Path(root)
        base = len(root.parts)
        for folder, subfolders, files in os.walk(root):
            if clock() > deadline:
                break
            here = Path(folder)
            if len(here.parts) - base >= depth:
                subfolders[:] = []
            subfolders[:] = [d for d in subfolders if not d.startswith((".", "$")) and d.lower() not in
                             {"appdata", "windows", "program files", "program files (x86)", "node_modules"}]
            count = sum(1 for name in files if name.lower().endswith(ACT_SUFFIXES) and not name.startswith("~$"))
            if count >= 5:
                found[str(here)] = count
    return [{"path": path, "acts": count} for path, count in sorted(found.items(), key=lambda kv: -kv[1])[:5]]


def scan(*, programs=installed_programs, mail_detect=None, roots=None, seconds: float = 8.0) -> dict:
    names = programs()
    matched, seen = [], set()
    for display in names:
        plain = display.lower().replace("ł", "l")
        for fragment, shown, kind, use in KNOWN:
            if fragment in plain and shown not in seen:
                seen.add(shown)
                matched.append({"name": display, "shown": shown, "kind": kind, "use": use})
                break
    mail = []
    if mail_detect is not None:
        try:
            mail = [{"kind": source.name.lower(), "label": source.name} for source in mail_detect()]
        except Exception:
            mail = []
    return {"mail": mail, "programs": matched,
            "acts": act_folders(default_roots() if roots is None else roots, seconds=seconds),
            "scanned": int(time.time())}
