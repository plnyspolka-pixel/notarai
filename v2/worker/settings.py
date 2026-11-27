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
    # Replace identifiers and listed names with placeholders before text leaves the computer.
    pseudonymize: bool = True
    # Owner's decision 27.11.2026: V2 works on the office's real cases. A release gate set by the
    # installation, never switched from the application.
    real_data_approved: bool = True


class AccountSettings(_Strict):
    region: str = "eu-central-1"
    user_pool_id: str
    client_id: str = Field(min_length=1, max_length=128)
    identity_pool_id: str


class ReplicaSettings(_Strict):
    enabled: bool = False
    bucket: str = Field(default="", max_length=63)
    region: str = "eu-central-1"
    every_hours: int = Field(default=24, ge=1, le=168)     # how often an encrypted copy goes to Frankfurt
    keep_days: int = Field(default=30, ge=0, le=3650)      # 0: copies are never deleted

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
        local = r"127\.0\.0\.1:\d{1,5}(/[\w./-]*)?"       # development relay and page only
        public = r"[A-Za-z0-9.-]+(:\d{1,5})?(/[\w./-]*)?"
        if not re.fullmatch(f"wss://{public}|ws://{local}", self.relay_url):
            raise ValueError("relay must use TLS")
        if not re.fullmatch(f"https://{public}|http://{local}", self.pocket_url):
            raise ValueError("Pocket must be served over HTTPS")

    def relay_origin(self) -> str | None:
        if not self.enabled:
            return None
        return re.match(r"wss?://[^/]+", self.relay_url).group(0)


class SpeechSettings(_Strict):
    # chmura: Amazon Transcribe in the EU (the office computer does no speech work);
    # lokalnie: faster-whisper on this computer (downloads a model, uses the processor).
    where: str = Field(default="chmura", pattern=r"^(chmura|lokalnie)$")
    # The EU bucket of the notarai-v2-mowa stack: the slower second way when streaming is blocked.
    bucket: str = Field(default="notarai-v2-mowa-127621462971", max_length=63, pattern=r"^([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])?$")
    model: str = Field(default="small", pattern=r"^(tiny|base|small|medium|large-v3|turbo)$")


class ListenSettings(_Strict):
    enabled: bool = False
    paused: bool = False
    gap_seconds: int = Field(default=120, ge=30, le=900)     # quiet this long ends a conversation


class MailSettings(_Strict):
    source: str | None = Field(default=None, pattern=r"^(thunderbird|outlook|folder)$")
    path: str | None = Field(default=None, max_length=400)


class CalendarSettings(_Strict):
    # Owner's decision 27.11.2026: the calendar is the same here and in the web version, both ways.
    web_sync: bool = True
    web_url: str = Field(default="https://app.notarai.pl", max_length=200,
                         pattern=r"^(https://[A-Za-z0-9.-]+(:\d{1,5})?|http://127\.0\.0\.1:\d{1,5})$")


class AgentSettings(_Strict):
    """The computer agent (owner's decisions 27.11.2026). All of it can be switched off on the station."""
    browser: str = Field(default="edge", pattern=r"^(edge|chrome)$")   # which browser NotarAI drives
    screen: bool = True         # the agent may look at the screen (a screenshot goes to the model in the EU as it is)
    commands: bool = True       # the agent may run a program with arguments (never a shell)
    # The NotarAI browser works out of sight (its window is kept off the screen) and is shown only when the
    # notary has to log in, look at the result or sign (owner's decision 27.11.2026, 2.8.0).
    background: bool = True


class Settings(_Strict):
    agent: AgentSettings = AgentSettings()
    ai: AiSettings = AiSettings()
    account: AccountSettings | None = None
    replica: ReplicaSettings = ReplicaSettings()
    tunnel: TunnelSettings = TunnelSettings()
    mail: MailSettings = MailSettings()
    speech: SpeechSettings = SpeechSettings()
    listen: ListenSettings = ListenSettings()
    calendar: CalendarSettings = CalendarSettings()
    backup_dir: str | None = None
    acts_dir: str | None = Field(default=None, max_length=400)     # where the office keeps its acts
    learn: bool = True                                             # learning mode, visible in the window
    station_name: str = Field(default="", max_length=60)          # e.g. Gabinet, Sekretariat
    allow_screen: bool = False                                     # other stations may see this screen
    device_names: dict[str, str] = Field(default_factory=dict)     # printer/scanner id -> the office's name
    # Owner's decision 27.11.2026: a command is the approval ("wyślij pocztę" sends). When true, the
    # program asks "Tak / Nie" before irreversible actions as it did before.
    confirm: bool = Field(default_factory=lambda: os.environ.get("NOTARAI_ALWAYS_CONFIRM") == "1")
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
