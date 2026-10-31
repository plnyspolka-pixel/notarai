"""Logowanie uzytkownikow kancelarii przez Amazon Cognito.

Hasla przechowuje i sprawdza Cognito. Aplikacja nigdy ich nie zapisuje ani
nie loguje - przechodza przez pamiec tylko na czas jednego zadania.

Po zalogowaniu przegladarka dostaje token tozsamosci (JWT) i dolacza go do
kazdego zadania. Token niesie adres e-mail i kancelarie, wiec nie trzeba
trzymac zadnej sesji po stronie serwera.

Zero danych osobowych w logach: zapisujemy sam wynik operacji.
"""
import logging
import os
import re

import config

log = logging.getLogger("pieczapp.logowanie")

PULA = os.getenv("PIECZAPP_COGNITO_POOL", "")
KLIENT = os.getenv("PIECZAPP_COGNITO_KLIENT", "")

# Token JWT ma trzy czesci rozdzielone kropka. Po tym odrozniamy go od
# tokenu pomocnika i awaryjnego tokenu administratora.
_JWT = re.compile(r"^[\w-]+\.[\w-]+\.[\w-]+$")

_cognito = None
_klucze = None


class BladLogowania(RuntimeError):
    """Komunikat nadaje sie do pokazania uzytkownikowi."""


def wlaczone() -> bool:
    return bool(PULA and KLIENT)


def czy_jwt(token: str) -> bool:
    return bool(_JWT.match(token or ""))


def _klient():
    global _cognito
    if _cognito is None:
        import boto3
        if config.PROFIL_AWS:
            sesja = boto3.Session(profile_name=config.PROFIL_AWS, region_name=config.REGION)
        else:
            sesja = boto3.Session(region_name=config.REGION)
        _cognito = sesja.client("cognito-idp")
    return _cognito


def _weryfikator():
    """Klucze publiczne puli, pobierane raz i trzymane w pamieci."""
    global _klucze
    if _klucze is None:
        from jwt import PyJWKClient
        _klucze = PyJWKClient(
            f"https://cognito-idp.{config.REGION}.amazonaws.com/{PULA}/.well-known/jwks.json",
            cache_keys=True,
        )
    return _klucze


# --- logowanie --------------------------------------------------------------


def zaloguj(email: str, haslo: str) -> dict:
    """Zwraca {"token": ...} albo {"wymagane_nowe_haslo": True, "sesja": ...}."""
    try:
        odp = _klient().initiate_auth(
            ClientId=KLIENT,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": haslo},
        )
    except Exception as blad:
        nazwa = type(blad).__name__
        if nazwa in ("NotAuthorizedException", "UserNotFoundException"):
            log.info("nieudane logowanie")
            raise BladLogowania("Nieprawidlowy adres e-mail albo haslo.") from blad
        if nazwa == "PasswordResetRequiredException":
            raise BladLogowania(
                "Haslo wymaga zresetowania. Uzyj opcji odzyskiwania hasla."
            ) from blad
        if nazwa == "TooManyRequestsException":
            raise BladLogowania("Za duzo prob. Odczekaj chwile.") from blad
        raise

    if odp.get("ChallengeName") == "NEW_PASSWORD_REQUIRED":
        return {"wymagane_nowe_haslo": True, "sesja": odp["Session"]}
    log.info("udane logowanie")
    return _wynik(odp)


def ustaw_nowe_haslo(email: str, nowe_haslo: str, sesja: str) -> dict:
    """Pierwsze logowanie: zamiana hasla tymczasowego na wlasne."""
    try:
        odp = _klient().respond_to_auth_challenge(
            ClientId=KLIENT,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=sesja,
            ChallengeResponses={"USERNAME": email, "NEW_PASSWORD": nowe_haslo},
        )
    except Exception as blad:
        raise _blad_hasla(blad) from blad
    log.info("ustawiono haslo przy pierwszym logowaniu")
    return _wynik(odp)


def _wynik(odp: dict) -> dict:
    """Token tozsamosci dla przegladarki i - osobno - token odnawiania.

    Token odnawiania (30 dni) nie trafia do JavaScriptu: serwer odklada go w
    ciasteczku HttpOnly. Dzieki niemu przegladarka sama dostaje nowy token
    tozsamosci, zanim stary wygasnie, i notariusz loguje sie raz na miesiac,
    a nie co 8 godzin.
    """
    wynik = odp.get("AuthenticationResult") or {}
    if not wynik.get("IdToken"):
        raise BladLogowania("Logowanie nie zakonczylo sie poprawnie.")
    return {"token": wynik["IdToken"], "wygasa_za": wynik.get("ExpiresIn", 3600),
            "odnowienie": wynik.get("RefreshToken", "")}


def odnow(token_odnowienia: str) -> dict:
    """Nowy token tozsamosci z tokenu odnawiania. Bez hasla."""
    if not token_odnowienia:
        raise BladLogowania("Zaloguj sie ponownie.")
    try:
        odp = _klient().initiate_auth(
            ClientId=KLIENT,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": token_odnowienia},
        )
    except Exception as blad:
        if type(blad).__name__ in ("NotAuthorizedException", "UserNotFoundException"):
            # wygasl, zostal uniewazniony albo konto wylaczono
            raise BladLogowania("Sesja wygasla. Zaloguj sie ponownie.") from blad
        raise
    wynik = _wynik(odp)
    # Cognito bez rotacji nie zwraca nowego tokenu odnawiania - stary dziala dalej.
    wynik["odnowienie"] = wynik["odnowienie"] or token_odnowienia
    return wynik


def wyloguj(token_odnowienia: str) -> None:
    """Uniewaznia token odnawiania. Bledy pomijamy - ciasteczko i tak znika."""
    if not token_odnowienia:
        return
    try:
        _klient().revoke_token(Token=token_odnowienia, ClientId=KLIENT)
    except Exception as blad:  # noqa: BLE001
        log.info("wylogowanie: nie uniewazniono tokenu (%s)", type(blad).__name__)


# --- odzyskiwanie hasla -----------------------------------------------------


def wyslij_kod(email: str) -> None:
    """Wysyla kod na adres uzytkownika.

    Nie zdradzamy, czy adres istnieje - odpowiedz jest zawsze taka sama.
    """
    try:
        _klient().forgot_password(ClientId=KLIENT, Username=email)
        log.info("wyslano kod odzyskiwania hasla")
    except Exception as blad:
        nazwa = type(blad).__name__
        if nazwa in ("UserNotFoundException", "InvalidParameterException"):
            log.info("kod odzyskiwania: adres nieznany albo konto nieaktywne")
            return
        if nazwa in ("LimitExceededException", "TooManyRequestsException"):
            raise BladLogowania(
                "Za duzo prob odzyskiwania hasla. Sprobuj za kilkanascie minut."
            ) from blad
        raise


def ustaw_haslo_kodem(email: str, kod: str, nowe_haslo: str) -> None:
    try:
        _klient().confirm_forgot_password(
            ClientId=KLIENT, Username=email, ConfirmationCode=kod, Password=nowe_haslo
        )
        log.info("haslo ustawione kodem z wiadomosci")
    except Exception as blad:
        nazwa = type(blad).__name__
        if nazwa in ("CodeMismatchException", "ExpiredCodeException"):
            raise BladLogowania("Kod jest nieprawidlowy albo wygasl.") from blad
        raise _blad_hasla(blad) from blad


def _blad_hasla(blad: Exception) -> Exception:
    nazwa = type(blad).__name__
    if nazwa == "InvalidPasswordException":
        return BladLogowania(
            f"Haslo za slabe: minimum {os.getenv('PIECZAPP_MIN_HASLO', '12')} znakow, "
            "w tym wielka litera, mala litera i cyfra."
        )
    if nazwa in ("NotAuthorizedException", "ExpiredCodeException"):
        return BladLogowania("Sesja wygasla. Zacznij logowanie od poczatku.")
    return blad


# --- token ------------------------------------------------------------------


def dane_z_tokenu(token: str) -> dict:
    """Sprawdza podpis i waznosc tokenu. Zwraca {"email", "kancelaria"}."""
    import jwt
    try:
        klucz = _weryfikator().get_signing_key_from_jwt(token)
        dane = jwt.decode(
            token,
            klucz.key,
            algorithms=["RS256"],
            audience=KLIENT,
            issuer=f"https://cognito-idp.{config.REGION}.amazonaws.com/{PULA}",
        )
    except Exception as blad:
        raise BladLogowania("Token wygasl albo jest nieprawidlowy.") from blad
    if dane.get("token_use") != "id":
        raise BladLogowania("Nieprawidlowy rodzaj tokenu.")
    kancelaria = dane.get("custom:kancelaria")
    if not kancelaria:
        raise BladLogowania("Konto nie jest przypisane do zadnej kancelarii.")
    return {"email": dane.get("email", ""), "kancelaria": kancelaria}


# --- administracja ----------------------------------------------------------


def utworz_uzytkownika(email: str, kancelaria: str) -> None:
    """Zaklada konto i wysyla zaproszenie z haslem tymczasowym."""
    try:
        _klient().admin_create_user(
            UserPoolId=PULA,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "custom:kancelaria", "Value": kancelaria},
            ],
            DesiredDeliveryMediums=["EMAIL"],
        )
        log.info("utworzono konto uzytkownika w kancelarii %s", kancelaria)
    except Exception as blad:
        if type(blad).__name__ == "UsernameExistsException":
            raise BladLogowania("Konto o tym adresie juz istnieje.") from blad
        raise


def ponow_zaproszenie(email: str) -> None:
    """Wysyla zaproszenie jeszcze raz, z nowym haslem tymczasowym.

    Zaproszenia z domyslnej wysylki Cognito czesto trafiaja do spamu albo
    wygasaja, zanim ktos je otworzy. Ponowienie musi byc jednym kliknieciem.
    """
    try:
        _klient().admin_create_user(
            UserPoolId=PULA, Username=email,
            MessageAction="RESEND", DesiredDeliveryMediums=["EMAIL"],
        )
        log.info("ponowiono zaproszenie")
    except Exception as blad:
        nazwa = type(blad).__name__
        if nazwa == "UserNotFoundException":
            raise BladLogowania("Nie ma konta o tym adresie.") from blad
        if nazwa == "UnsupportedUserStateException":
            raise BladLogowania(
                "To konto ma juz ustawione haslo. Jesli go nie pamieta, "
                "niech uzyje opcji Nie pamietam hasla."
            ) from blad
        raise


def usun_uzytkownika(email: str) -> None:
    """Usuwa konto. Brak konta nie jest bledem - cel i tak osiagniety."""
    try:
        _klient().admin_delete_user(UserPoolId=PULA, Username=email)
        log.info("usunieto konto uzytkownika")
    except Exception as blad:
        if type(blad).__name__ != "UserNotFoundException":
            raise
