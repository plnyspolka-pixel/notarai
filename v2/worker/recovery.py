"""Recovery code, encrypted backup and restore for the local vault.

The master key lives in the Windows profile (DPAPI). Losing that profile must
not lose the vault, so a second copy of the master key is wrapped under a
recovery code that the notary prints and keeps off the computer. A backup file
holds the encrypted database plus that wrapped key: it is useless without the
code and contains no plaintext.
"""
import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .local_secrets import read_secret, replace_secret, secret_path, write_new_secret
from .vault import Vault, derive

RECOVERY_FILE = "vault.key.recovery"
FORMAT = 1
AAD = b"notarai-v2:recovery:v1"
MAX_DB = 64 * 1024 * 1024 * 1024
_NAMES = {"manifest.json", RECOVERY_FILE, "vault.sqlite3"}


class RecoveryError(Exception):
    """Message is safe to show to the operator."""


# ---------------------------------------------------------------- recovery code
def new_code() -> tuple[str, bytes]:
    secret = secrets.token_bytes(32)
    return format_code(secret), secret


def format_code(secret: bytes) -> str:
    raw = secret + hashlib.sha256(b"notarai-v2 code" + secret).digest()[:3]
    text = base64.b32encode(raw).decode()  # 35 bytes -> 56 characters, no padding
    return "-".join(text[i:i + 4] for i in range(0, len(text), 4))


def parse_code(code: str) -> bytes:
    text = "".join(c for c in code.upper() if c.isalnum())
    # Characters that are easy to confuse on a printout.
    text = text.replace("0", "O").replace("1", "I").replace("8", "B")
    try:
        raw = base64.b32decode(text)
    except ValueError:
        raise RecoveryError("Kod odzyskiwania jest niepoprawny.") from None
    secret, check = raw[:32], raw[32:]
    if len(raw) != 35 or not hmac.compare_digest(check, hashlib.sha256(b"notarai-v2 code" + secret).digest()[:3]):
        raise RecoveryError("Kod odzyskiwania jest niepoprawny (literówka?).")
    return secret


def wrap_master(master: bytes, secret: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(derive(secret, "recovery")).encrypt(nonce, master, AAD)


def unwrap_master(blob: bytes, secret: bytes) -> bytes:
    try:
        return AESGCM(derive(secret, "recovery")).decrypt(blob[:12], blob[12:], AAD)
    except InvalidTag:
        raise RecoveryError("Ten kod odzyskiwania nie pasuje do tego sejfu.") from None


def enrolled(home: Path) -> bool:
    return (home / RECOVERY_FILE).is_file()


def enroll(home: Path, *, replace: bool = False) -> str:
    """Create the recovery code. Returns it once; it is not stored anywhere."""
    target = home / RECOVERY_FILE
    if target.exists() and not replace:
        raise RecoveryError("Kod odzyskiwania już istnieje. Użyj wymiany kodu, aby wydać nowy.")
    code, secret = new_code()
    _write_atomic(target, wrap_master(read_secret(home, "vault.key"), secret))
    return code


def _write_atomic(target: Path, data: bytes) -> None:
    temporary = target.with_name(target.name + ".new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, target)


# ---------------------------------------------------------------- backup
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_mac(master: bytes, manifest: dict) -> str:
    body = json.dumps({k: v for k, v in manifest.items() if k != "mac"}, sort_keys=True).encode()
    return hmac.new(derive(master, "backup"), body, hashlib.sha256).hexdigest()


def backup(home: Path, destination: Path, *, action: str | None = "backup") -> dict:
    """Write one backup file. Refuses to overwrite and to run without a recovery code."""
    if not enrolled(home):
        raise RecoveryError("Najpierw utwórz kod odzyskiwania: bez niego kopii nie da się odtworzyć.")
    destination = Path(destination)
    if destination.exists():
        raise RecoveryError("Plik kopii już istnieje. Wybierz nową nazwę.")
    master = read_secret(home, "vault.key")
    vault = Vault(home, master)
    with tempfile.TemporaryDirectory(dir=home) as scratch:
        snapshot = Path(scratch) / "vault.sqlite3"
        vault.snapshot(snapshot)
        counts = _verify_snapshot(Path(scratch), master)
        wrapped = (home / RECOVERY_FILE).read_bytes()
        manifest = {
            "format": FORMAT, "created": int(time.time()),
            "vault_sha256": _sha256(snapshot),
            "recovery_sha256": hashlib.sha256(wrapped).hexdigest(),
            **counts,
        }
        manifest["mac"] = _manifest_mac(master, manifest)
        partial = destination.with_name(destination.name + ".part")
        try:
            with zipfile.ZipFile(partial, "x", zipfile.ZIP_STORED, allowZip64=True) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
                archive.writestr(RECOVERY_FILE, wrapped)
                archive.write(snapshot, "vault.sqlite3")
            os.replace(partial, destination)
        finally:
            partial.unlink(missing_ok=True)
    if action:
        vault.log("local-admin", action)
    return manifest


def _verify_snapshot(directory: Path, master: bytes) -> dict:
    return Vault(directory, master).verify()


def inspect(source: Path) -> dict:
    """Read the manifest without the recovery code (no secrets involved)."""
    with _open_backup(source) as archive:
        return _manifest(archive)


def _open_backup(source: Path) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile):
        raise RecoveryError("To nie jest plik kopii NotarAI albo jest uszkodzony.") from None
    entries = archive.infolist()
    if {e.filename for e in entries} != _NAMES or len(entries) != len(_NAMES) or any(
        e.compress_type != zipfile.ZIP_STORED or e.flag_bits & 1 for e in entries
    ) or archive.getinfo("vault.sqlite3").file_size > MAX_DB:
        archive.close()
        raise RecoveryError("To nie jest plik kopii NotarAI albo jest uszkodzony.")
    return archive


def _manifest(archive) -> dict:
    try:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest["format"] != FORMAT:
            raise RecoveryError("Kopia pochodzi z nowszej wersji NotarAI.")
        return manifest
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile):
        raise RecoveryError("To nie jest plik kopii NotarAI albo jest uszkodzony.") from None


def restore(source: Path, home: Path, code: str) -> dict:
    """Rebuild a vault in an empty directory. Returns counts and the new local API token."""
    secret = parse_code(code)
    home = Path(home)
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(home.iterdir()):
        raise RecoveryError("Katalog docelowy nie jest pusty. Odtwarzanie nigdy nie nadpisuje istniejącego sejfu.")
    with _open_backup(source) as archive:
        manifest = _manifest(archive)
        try:
            wrapped = archive.read(RECOVERY_FILE)
        except zipfile.BadZipFile:
            raise RecoveryError("Kopia jest uszkodzona (klucz).") from None
        if hashlib.sha256(wrapped).hexdigest() != manifest.get("recovery_sha256"):
            raise RecoveryError("Kopia jest uszkodzona (klucz).")
        master = unwrap_master(wrapped, secret)
        if not hmac.compare_digest(_manifest_mac(master, manifest), str(manifest.get("mac"))):
            raise RecoveryError("Kopia jest uszkodzona albo została zmieniona.")
        created = []
        try:
            database = home / "vault.sqlite3"
            created.append(database)
            try:
                with archive.open("vault.sqlite3") as src, database.open("xb") as dst:
                    for block in iter(lambda: src.read(1 << 20), b""):
                        dst.write(block)
            except (zipfile.BadZipFile, EOFError):
                raise RecoveryError("Kopia jest uszkodzona (baza).") from None
            if _sha256(database) != manifest["vault_sha256"]:
                raise RecoveryError("Kopia jest uszkodzona (baza).")
            try:
                counts = Vault(home, master).verify()
            except (InvalidTag, ValueError, KeyError, sqlite3.Error):
                raise RecoveryError("Kopia nie przeszła sprawdzenia: nie wszystkie dokumenty dają się odczytać.") from None
            token = secrets.token_urlsafe(48)
            # Listed before writing, in both possible forms, so a failure never leaves the key behind.
            created += [home / name for name in ("vault.key", "vault.key.dpapi", "api.token", "api.token.dpapi")]
            write_new_secret(home, "vault.key", master)
            write_new_secret(home, "api.token", token.encode())
            _write_atomic(home / RECOVERY_FILE, wrapped)
        except BaseException:
            for path in created + [home / RECOVERY_FILE]:
                Path(path).unlink(missing_ok=True)
            raise
    Vault(home, master).log("local-admin", "restore")
    return {**counts, "token": token, "backup_created": manifest["created"]}


def rotate_master(home: Path) -> str:
    """New master key and new recovery code, e.g. after a lost device or a leaked printout.

    Earlier backups stay readable only with the earlier code.
    """
    from .local_lock import Busy, acquire

    try:
        lock = acquire(home)
    except Busy:
        # A running worker keeps the old key in memory and would write data nobody can read later.
        raise RecoveryError("Zamknij NotarAI na tym komputerze, zanim wymienisz klucz sejfu.") from None
    try:
        return _rotate_locked(home)
    finally:
        lock.close()


def _rotate_locked(home: Path) -> str:
    old = read_secret(home, "vault.key")
    new = secrets.token_bytes(32)
    code, secret = new_code()
    vault = Vault(home, old)
    # Order matters: until the OS secret is replaced the old key still opens the vault,
    # so the rewrap and the secret swap are bracketed by a journal file.
    journal = home / "vault.key.rotating"
    _write_atomic(journal, wrap_master(new, old))
    vault.rotate(new)
    replace_secret(home, "vault.key", new)
    _write_atomic(home / RECOVERY_FILE, wrap_master(new, secret))
    journal.unlink()
    return code


def finish_interrupted_rotation(home: Path) -> bool:
    """Complete a rotation that stopped between the rewrap and the secret swap."""
    journal = Path(home) / "vault.key.rotating"
    if not journal.exists():
        return False
    home = Path(home)
    current = read_secret(home, "vault.key")
    try:
        new = unwrap_master(journal.read_bytes(), current)
    except RecoveryError:
        # The OS secret already holds the new key; only the recovery copy may be stale.
        new = None
    if new is None:
        (home / RECOVERY_FILE).unlink(missing_ok=True)
    else:
        try:
            Vault(home, current).verify()  # rewrap never happened
        except (InvalidTag, ValueError):
            Vault(home, new).verify()
            replace_secret(home, "vault.key", new)
            (home / RECOVERY_FILE).unlink(missing_ok=True)
    journal.unlink()
    return True


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    from .init_vault import home_path

    parser = argparse.ArgumentParser(description="Kod odzyskiwania i kopia zapasowa sejfu NotarAI V2")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("enroll", help="utwórz kod odzyskiwania")
    sub.add_parser("new-code", help="wydaj nowy kod (ten sam klucz sejfu)")
    sub.add_parser("rotate", help="nowy klucz sejfu i nowy kod")
    sub.add_parser("verify", help="sprawdź, czy każdy dokument daje się odczytać")
    backup_cmd = sub.add_parser("backup", help="zapisz kopię do pliku")
    backup_cmd.add_argument("destination", type=Path)
    restore_cmd = sub.add_parser("restore", help="odtwórz sejf w pustym katalogu NOTARAI_V2_HOME")
    restore_cmd.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    home = home_path()
    try:
        if args.action == "restore":
            code = os.environ.get("NOTARAI_V2_RECOVERY_CODE") or getpass.getpass("Kod odzyskiwania: ")
            result = restore(args.source, home, code)
            print(f"Odtworzono dokumentów: {result['documents']}, wersji: {result['revisions']}.")
            print("Sparuj urządzenia ponownie; dawne dostępy nie zostały przeniesione.")
            return 0
        finish_interrupted_rotation(home)
        if args.action in {"enroll", "new-code", "rotate"}:
            code = rotate_master(home) if args.action == "rotate" else enroll(home, replace=args.action == "new-code")
            print("Kod odzyskiwania (wydrukuj i przechowuj poza komputerem; nie pokażemy go ponownie):")
            print(code)
        elif args.action == "verify":
            print(json.dumps(Vault(home, read_secret(home, "vault.key")).verify()))
        elif args.action == "backup":
            manifest = backup(home, args.destination)
            print(f"Kopia zapisana. Dokumentów: {manifest['documents']}, wersji: {manifest['revisions']}.")
    except RecoveryError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, InvalidTag, sqlite3.Error):
        print("Nie udało się otworzyć sejfu.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
