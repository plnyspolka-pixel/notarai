"""Short-lived AWS credentials for this workstation, obtained from the office's NotarAI login.

No long-lived AWS key is ever installed. The notary signs in to the Cognito user
pool; the identity pool exchanges that sign-in for credentials that last about an
hour and allow only Bedrock model calls in the EU (infra/notarai-v2-bedrock.yaml).
Only the refresh token is kept, protected by the OS secret store. The password,
identity tokens and AWS credentials stay in memory.
"""
import base64
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .local_secrets import delete_secret, read_secret, secret_path, store_secret
from .policy import EU_REGIONS

REFRESH_SECRET = "cognito.refresh"


class LoginError(Exception):
    """Fixed message, safe to show."""


class ChallengeRequired(LoginError):
    def __init__(self, kind: str):
        super().__init__({"mfa": "Podaj kod z aplikacji uwierzytelniającej.",
                          "new_password": "Ustaw własne hasło przy pierwszym logowaniu."}[kind])
        self.kind = kind


@dataclass(frozen=True)
class AccountConfig:
    region: str
    user_pool_id: str
    client_id: str
    identity_pool_id: str

    def __post_init__(self):
        if self.region not in EU_REGIONS or not self.user_pool_id.startswith(self.region + "_") \
                or not self.identity_pool_id.startswith(self.region + ":"):
            raise ValueError("NotarAI sign-in must live in one EU region")


def _unsigned_factory(service, region):
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config

    return boto3.client(service, region_name=region, config=Config(signature_version=UNSIGNED))


def _expiry(jwt: str) -> float:
    try:
        payload = jwt.split(".")[1]
        return float(json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["exp"])
    except (IndexError, KeyError, ValueError, TypeError):
        raise LoginError("Logowanie zwróciło nieczytelny token.") from None


class Account:
    def __init__(self, home: Path, config: AccountConfig, *, unsigned_factory=_unsigned_factory, clock=time.time):
        self._home, self._config, self._clock = Path(home), config, clock
        self._idp = unsigned_factory("cognito-idp", config.region)
        self._identity = unsigned_factory("cognito-identity", config.region)
        self._lock = threading.Lock()
        self._id_token: str | None = None
        self._id_expires = 0.0
        self._credentials: dict | None = None
        self._identity_id = ""

    # ------------------------------------------------------------ sign-in
    @property
    def signed_in(self) -> bool:
        return secret_path(self._home, REFRESH_SECRET).exists()

    def login(self, email: str, password: str, *, mfa_code: str | None = None, new_password: str | None = None) -> None:
        try:
            response = self._idp.initiate_auth(
                ClientId=self._config.client_id, AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": email, "PASSWORD": password},
            )
            for _ in range(2):
                challenge = response.get("ChallengeName")
                if not challenge:
                    break
                if challenge == "NEW_PASSWORD_REQUIRED":
                    if not new_password:
                        raise ChallengeRequired("new_password")
                    answers = {"USERNAME": email, "NEW_PASSWORD": new_password}
                elif challenge == "SOFTWARE_TOKEN_MFA":
                    if not mfa_code:
                        raise ChallengeRequired("mfa")
                    answers = {"USERNAME": email, "SOFTWARE_TOKEN_MFA_CODE": mfa_code}
                else:
                    raise LoginError("To konto wymaga sposobu logowania, którego stanowisko nie obsługuje.")
                response = self._idp.respond_to_auth_challenge(
                    ClientId=self._config.client_id, ChallengeName=challenge,
                    Session=response["Session"], ChallengeResponses=answers,
                )
            result = response["AuthenticationResult"]
            refresh, id_token = result["RefreshToken"], result["IdToken"]
        except LoginError:
            raise
        except Exception:
            # Cognito error text can echo the e-mail address; never pass it on.
            raise LoginError("Nie udało się zalogować. Sprawdź adres e-mail i hasło.") from None
        store_secret(self._home, REFRESH_SECRET, refresh.encode())
        with self._lock:
            self._id_token, self._id_expires, self._credentials = id_token, _expiry(id_token), None

    def logout(self) -> None:
        with self._lock:
            self._id_token, self._credentials = None, None
        if self.signed_in:
            try:
                self._idp.revoke_token(
                    Token=read_secret(self._home, REFRESH_SECRET).decode(), ClientId=self._config.client_id)
            except Exception:
                pass  # the local copy is removed regardless
        delete_secret(self._home, REFRESH_SECRET)

    # ------------------------------------------------------------ tokens
    def _fresh_id_token(self) -> str:
        if self._id_token and self._clock() < self._id_expires - 60:
            return self._id_token
        if not self.signed_in:
            raise LoginError("Zaloguj się do NotarAI, aby korzystać z AI.")
        try:
            result = self._idp.initiate_auth(
                ClientId=self._config.client_id, AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters={"REFRESH_TOKEN": read_secret(self._home, REFRESH_SECRET).decode()},
            )["AuthenticationResult"]
        except Exception:
            raise LoginError("Sesja wygasła. Zaloguj się ponownie.") from None
        if result.get("RefreshToken"):  # pools with refresh-token rotation
            store_secret(self._home, REFRESH_SECRET, result["RefreshToken"].encode())
        self._id_token, self._id_expires = result["IdToken"], _expiry(result["IdToken"])
        return self._id_token

    def credentials(self) -> dict:
        """AWS credentials valid for at least five more minutes."""
        with self._lock:
            if self._credentials and self._clock() < self._credentials["expires"] - 300:
                return dict(self._credentials)
            provider = f"cognito-idp.{self._config.region}.amazonaws.com/{self._config.user_pool_id}"
            logins = {provider: self._fresh_id_token()}
            try:
                identity = self._identity.get_id(IdentityPoolId=self._config.identity_pool_id, Logins=logins)
                issued = self._identity.get_credentials_for_identity(
                    IdentityId=identity["IdentityId"], Logins=logins)["Credentials"]
                self._identity_id = identity["IdentityId"]
                expires = issued["Expiration"]
                self._credentials = {
                    "access_key": issued["AccessKeyId"], "secret_key": issued["SecretKey"],
                    "token": issued["SessionToken"],
                    "expires": expires.timestamp() if hasattr(expires, "timestamp") else float(expires),
                }
            except LoginError:
                raise
            except Exception:
                raise LoginError("Nie udało się uzyskać dostępu do AI dla tego konta.") from None
            return dict(self._credentials)

    def identity_id(self) -> str:
        """This office's identity in the pool; also its private prefix for off-site copies."""
        self.credentials()
        return self._identity_id

    def client_factory(self, region: str | None = None):
        """`factory(service)` for worker.inference.Inference; clients always carry fresh credentials."""
        region = region or self._config.region
        if region not in EU_REGIONS:
            raise ValueError("EU regions only")

        def factory(service: str):
            import boto3

            current = self.credentials()
            return boto3.client(
                service, region_name=region, aws_access_key_id=current["access_key"],
                aws_secret_access_key=current["secret_key"], aws_session_token=current["token"],
            )
        return factory
