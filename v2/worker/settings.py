"""Non-secret workstation settings in settings.json. Missing file means everything optional is off."""
import json
import os
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .aws_credentials import AccountConfig
from .policy import EU_REGIONS, check_static


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AiSettings(_Strict):
    enabled: bool = False
    region: str = "eu-central-1"
    model: str = "eu.anthropic.claude-sonnet-4-6"
    # Stays false until the release gates in README.md are met; while false the
    # worker labels itself synthetic-only.
    real_data_approved: bool = False


class AccountSettings(_Strict):
    region: str = "eu-central-1"
    user_pool_id: str
    client_id: str = Field(min_length=1, max_length=128)
    identity_pool_id: str


class ReplicaSettings(_Strict):
    enabled: bool = False
    bucket: str = Field(default="", max_length=63)
    region: str = "eu-central-1"

    def check(self) -> None:
        if self.enabled and (self.region not in EU_REGIONS or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.bucket)):
            raise ValueError("off-site copies need an EU bucket")


class TunnelSettings(_Strict):
    """Remote access for paired devices through the relay. Off by default."""
    enabled: bool = False
    relay_url: str = Field(default="", max_length=300)
    pocket_url: str = Field(default="", max_length=300)   # where the Pocket page is served over HTTPS

    def check(self) -> None:
        if not self.enabled:
            return
        local = self.relay_url.startswith("ws://127.0.0.1:")      # development relay only
        if not (re.fullmatch(r"wss://[A-Za-z0-9.-]+(:\d+)?(/[\w./-]*)?", self.relay_url) or local):
            raise ValueError("relay must use TLS")
        if not (re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d+)?(/[\w./-]*)?", self.pocket_url)
                or self.pocket_url.startswith("http://127.0.0.1:")):
            raise ValueError("Pocket must be served over HTTPS")

    def relay_origin(self) -> str | None:
        if not self.enabled:
            return None
        return re.match(r"wss?://[^/]+", self.relay_url).group(0)


class Settings(_Strict):
    ai: AiSettings = AiSettings()
    account: AccountSettings | None = None
    replica: ReplicaSettings = ReplicaSettings()
    tunnel: TunnelSettings = TunnelSettings()
    backup_dir: str | None = None
    backup_reminder_days: int = Field(default=7, ge=1, le=90)

    def account_config(self) -> AccountConfig | None:
        if self.account is None:
            return None
        return AccountConfig(**self.account.model_dump())


def validate(data) -> Settings:
    try:
        settings = Settings.model_validate(data)
        check_static(settings.ai.region, settings.ai.model)
        settings.account_config()
        settings.tunnel.check()
        settings.replica.check()
    except (ValidationError, PermissionError, TypeError):
        raise ValueError("settings are invalid") from None
    return settings


def load(home: Path) -> Settings:
    path = Path(home) / "settings.json"
    if not path.exists():
        return Settings()
    try:
        return validate(json.loads(path.read_text(encoding="utf-8")))
    except ValueError:
        raise ValueError("settings.json is invalid") from None


def save(home: Path, settings: Settings) -> None:
    path = Path(home) / "settings.json"
    temporary = path.with_name("settings.json.new")
    temporary.write_text(json.dumps(settings.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
