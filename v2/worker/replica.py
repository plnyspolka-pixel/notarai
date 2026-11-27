"""Off-site copy: the same encrypted backup file, stored in the office's own S3 prefix in the EU.

The file is ciphertext that only the recovery code opens; NotarAI and AWS hold no key.
Uploads use the workstation's short-lived sign-in credentials, which can write only
under this identity's prefix (infra/notarai-v2-kopia.yaml).
"""
import tempfile
import time
from pathlib import Path

from . import recovery
from .policy import EU_REGIONS

SUFFIX = ".notarai-backup"
KEEP = 3                     # never fewer than this many copies, whatever the retention


class ReplicaError(Exception):
    """Fixed message, safe to show."""


class Replica:
    def __init__(self, home: Path, account, bucket: str, region: str, keep_days: int = 30):
        if region not in EU_REGIONS or not bucket:
            raise ValueError("off-site copies stay in the EU")
        self._home, self._account, self._bucket, self._region = Path(home), account, bucket, region
        self._keep_days = keep_days

    def _s3(self):
        return self._account.client_factory(self._region)("s3")

    def _prefix(self) -> str:
        return self._account.identity_id() + "/"

    def upload(self) -> dict:
        """Make a fresh backup and store it. Old copies beyond KEEP are removed."""
        name = time.strftime("notarai-%Y%m%d-%H%M%S", time.gmtime()) + SUFFIX
        try:
            s3, prefix = self._s3(), self._prefix()
            with tempfile.TemporaryDirectory(dir=self._home) as scratch:
                local = Path(scratch) / name
                manifest = recovery.backup(self._home, local, action=None)
                s3.upload_file(str(local), self._bucket, prefix + name,
                               ExtraArgs={"ServerSideEncryption": "AES256"})
            self._log()        # only a copy that actually left the building counts
            for stale in self.stale(self.list()):
                s3.delete_object(Bucket=self._bucket, Key=prefix + stale["name"])
        except recovery.RecoveryError:
            raise
        except Exception:
            raise ReplicaError("Nie udało się wysłać kopii poza kancelarię. Sprawdź połączenie i logowanie.") from None
        return {"file": name, "documents": manifest["documents"], "revisions": manifest["revisions"]}

    def stale(self, copies: list[dict]) -> list[dict]:
        """Copies older than the office's retention; the newest KEEP always stay. keep_days 0 keeps all."""
        if self._keep_days == 0:
            return []
        limit = time.strftime("notarai-%Y%m%d-%H%M%S", time.gmtime(time.time() - self._keep_days * 86400))
        return [copy for copy in copies[KEEP:] if copy["name"] < limit]

    def _log(self) -> None:
        from .local_secrets import read_secret
        from .vault import Vault

        Vault(self._home, read_secret(self._home, "vault.key")).log("local-admin", "offsite-backup")

    def list(self) -> list[dict]:
        """Newest first."""
        try:
            prefix = self._prefix()
            found = self._s3().list_objects_v2(Bucket=self._bucket, Prefix=prefix).get("Contents") or []
        except Exception:
            raise ReplicaError("Nie udało się odczytać listy kopii.") from None
        names = [{"name": item["Key"][len(prefix):], "size": item["Size"]} for item in found
                 if item["Key"].endswith(SUFFIX) and "/" not in item["Key"][len(prefix):]]
        return sorted(names, key=lambda item: item["name"], reverse=True)

    def download(self, name: str, destination: Path) -> None:
        """Fetch one copy, e.g. onto a new computer before `recovery restore`."""
        if "/" in name or "\\" in name or not name.endswith(SUFFIX) or Path(destination).exists():
            raise ReplicaError("Niepoprawna nazwa kopii albo plik docelowy już istnieje.")
        try:
            self._s3().download_file(self._bucket, self._prefix() + name, str(destination))
        except Exception:
            Path(destination).unlink(missing_ok=True)
            raise ReplicaError("Nie udało się pobrać kopii.") from None
