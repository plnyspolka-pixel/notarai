"""Workstation sign-in and short-lived credentials. Cognito is faked; no network."""
import base64
import json

import pytest

from worker.aws_credentials import Account, AccountConfig, ChallengeRequired, LoginError, REFRESH_SECRET
from worker.local_secrets import read_secret

CONFIG = AccountConfig("eu-central-1", "eu-central-1_Pool", "client", "eu-central-1:11111111-2222")


def jwt(exp):
    body = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"h.{body}.s"


class Idp:
    def __init__(self, now, challenge=None):
        self.now, self.challenge, self.calls, self.revoked, self.rotate = now, challenge, [], None, False

    def _result(self, with_refresh=True):
        result = {"IdToken": jwt(self.now[0] + 3600)}
        if with_refresh:
            result["RefreshToken"] = f"refresh-{len(self.calls)}"
        return {"AuthenticationResult": result}

    def initiate_auth(self, **kw):
        self.calls.append(kw)
        if kw["AuthFlow"] == "USER_PASSWORD_AUTH":
            if kw["AuthParameters"]["PASSWORD"] != "dobre":
                raise RuntimeError("Incorrect username or password for anna@example.pl")
            if self.challenge:
                return {"ChallengeName": self.challenge, "Session": "s"}
            return self._result()
        assert kw["AuthParameters"]["REFRESH_TOKEN"].startswith("refresh-")
        return self._result(with_refresh=self.rotate)

    def respond_to_auth_challenge(self, **kw):
        self.calls.append(kw)
        return self._result()

    def revoke_token(self, **kw):
        self.revoked = kw["Token"]


class Identity:
    def __init__(self, now):
        self.now, self.issued = now, 0

    def get_id(self, IdentityPoolId, Logins):
        assert list(Logins) == ["cognito-idp.eu-central-1.amazonaws.com/eu-central-1_Pool"]
        return {"IdentityId": "eu-central-1:id"}

    def get_credentials_for_identity(self, IdentityId, Logins):
        self.issued += 1
        return {"Credentials": {"AccessKeyId": f"AK{self.issued}", "SecretKey": "sk", "SessionToken": "st",
                                "Expiration": self.now[0] + 3600}}


def make(tmp_path, challenge=None):
    now = [1_000_000.0]
    idp, identity = Idp(now, challenge), Identity(now)
    account = Account(tmp_path, CONFIG, unsigned_factory=lambda service, region: idp if service == "cognito-idp" else identity,
                      clock=lambda: now[0])
    return account, idp, identity, now


def test_config_must_be_one_eu_region():
    with pytest.raises(ValueError):
        AccountConfig("us-east-1", "us-east-1_Pool", "c", "us-east-1:x")
    with pytest.raises(ValueError):
        AccountConfig("eu-central-1", "eu-west-1_Pool", "c", "eu-central-1:x")


def test_login_keeps_only_the_refresh_token(tmp_path):
    account, idp, identity, now = make(tmp_path)
    with pytest.raises(LoginError):
        account.credentials()
    with pytest.raises(LoginError) as error:
        account.login("anna@example.pl", "zle")
    assert "anna" not in str(error.value) and not account.signed_in
    account.login("anna@example.pl", "dobre")
    assert account.signed_in
    files = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert list(files) == [REFRESH_SECRET]
    assert b"dobre" not in files[REFRESH_SECRET] and b"anna" not in files[REFRESH_SECRET]
    first = account.credentials()
    assert first["access_key"] == "AK1" and account.credentials()["access_key"] == "AK1"
    assert identity.issued == 1


def test_credentials_and_tokens_are_renewed_before_expiry(tmp_path):
    account, idp, identity, now = make(tmp_path)
    account.login("anna@example.pl", "dobre")
    account.credentials()
    now[0] += 3600 - 299          # inside the five-minute margin
    assert account.credentials()["access_key"] == "AK2"
    assert idp.calls[-1]["AuthFlow"] == "USER_PASSWORD_AUTH"  # identity token still valid
    idp.rotate = True
    now[0] += 3600
    assert account.credentials()["access_key"] == "AK3"
    assert idp.calls[-1]["AuthFlow"] == "REFRESH_TOKEN_AUTH"
    assert read_secret(tmp_path, REFRESH_SECRET).decode() == f"refresh-{len(idp.calls)}"


def test_a_new_process_resumes_from_the_stored_refresh_token(tmp_path):
    account, idp, identity, now = make(tmp_path)
    account.login("anna@example.pl", "dobre")
    resumed = Account(tmp_path, CONFIG, unsigned_factory=lambda s, r: idp if s == "cognito-idp" else identity,
                      clock=lambda: now[0])
    assert resumed.credentials()["access_key"] == "AK1"


def test_challenges(tmp_path):
    account, idp, _, _ = make(tmp_path, challenge="SOFTWARE_TOKEN_MFA")
    with pytest.raises(ChallengeRequired) as error:
        account.login("anna@example.pl", "dobre")
    assert error.value.kind == "mfa" and not account.signed_in
    account.login("anna@example.pl", "dobre", mfa_code="123456")
    assert idp.calls[-1]["ChallengeResponses"]["SOFTWARE_TOKEN_MFA_CODE"] == "123456"
    (tmp_path / "b").mkdir()
    account, idp, _, _ = make(tmp_path / "b", challenge="NEW_PASSWORD_REQUIRED")
    with pytest.raises(ChallengeRequired) as error:
        account.login("anna@example.pl", "dobre")
    assert error.value.kind == "new_password"
    account, idp, _, _ = make(tmp_path / "b", challenge="SMS_MFA")
    with pytest.raises(LoginError):
        account.login("anna@example.pl", "dobre")


def test_logout_revokes_and_forgets(tmp_path):
    account, idp, _, _ = make(tmp_path)
    account.login("anna@example.pl", "dobre")
    token = read_secret(tmp_path, REFRESH_SECRET).decode()
    account.logout()
    assert idp.revoked == token and not account.signed_in and list(tmp_path.iterdir()) == []
    with pytest.raises(LoginError):
        account.credentials()
