"""Logowanie uzytkownikow kancelarii przez Amazon Cognito.

Hasla przechowuje i sprawdza Cognito. Aplikacja nigdy ich nie zapisuje ani
nie loguje - przechodza przez pamiec tylko na czas jednego zadania.

Po zalogowaniu przegladarka dostaje token tozsamosci (JWT) i dolacza go do
kazdego zadania. Token niesie adres e-mail i kancelarie, wiec nie trzeba
trzymac zadnej sesji po stronie serwera.

Zero danych osobowych w logach: zapisujemy sam wynik operacji.
"""
import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
import time

import config

log = logging.getLogger("pieczapp.logowanie")

PULA = os.getenv("PIECZAPP_COGNITO_POOL", "")
KLIENT = os.getenv("PIECZAPP_COGNITO_KLIENT", "")

# Logowanie kontem Google (pasek One Tap i przycisk). Identyfikator klienta
# OAuth jest publiczny. Klucz dzielimy z funkcja Lambda puli Cognito: po
# sprawdzeniu tokenu Google serwer podpisuje nim krotkotrwaly dowod, a Cognito
# wydaje za niego zwykla sesje - haslo w ogole nie bierze udzialu.
GOOGLE_KLIENT = os.getenv("PIECZAPP_GOOGLE_KLIENT", "")
_GOOGLE_KLUCZ = os.getenv("PIECZAPP_GOOGLE_KLUCZ", "")
_GOOGLE_WYDAWCY = ("https://accounts.google.com", "accounts.google.com")
_GOOGLE_KLUCZE = "https://www.googleapis.com/oauth2/v3/certs"
# Token z paska trafia do nas od razu po kliknieciu. Starszego nie przyjmujemy.
_GOOGLE_MAKS_WIEK = 10 * 60
# Adresy, dla ktorych Google jest dostawca poczty - tylko wtedy token Google
# dowodzi, ze ktos panuje nad skrzynka (gmail albo domena w Google Workspace).
_GOOGLE_DOMENY = ("gmail.com", "googlemail.com")
_BLAD_GOOGLE = "Logowanie przez Google nie powiodlo sie. Sprobuj ponownie."

# Token JWT ma trzy czesci rozdzielone kropka. Po tym odrozniamy go od
# tokenu pomocnika i awaryjnego tokenu administratora.
_JWT = re.compile(r"^[\w-]+\.[\w-]+\.[\w-]+$")

_cognito = None
_klucze = None
_klucze_google = None
_zuzyte_google: dict[str, float] = {}
_blokada_google = threading.Lock()


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


# --- logowanie kontem Google -------------------------------------------------


def google_wlaczone() -> bool:
    return bool(wlaczone() and GOOGLE_KLIENT and _GOOGLE_KLUCZ)


def _weryfikator_google():
    global _klucze_google
    if _klucze_google is None:
        from jwt import PyJWKClient
        _klucze_google = PyJWKClient(_GOOGLE_KLUCZE, cache_keys=True)
    return _klucze_google


def _jednorazowy(jti: str, wygasa: float) -> bool:
    """Ten sam token Google przyjmujemy raz (na proces; reszte robi limit wieku)."""
    teraz = time.time()
    with _blokada_google:
        for stary in [k for k, w in _zuzyte_google.items() if w < teraz]:
            del _zuzyte_google[stary]
        if jti in _zuzyte_google:
            return False
        _zuzyte_google[jti] = wygasa
        return True


def dane_z_google(token: str) -> dict:
    """Sprawdza token tozsamosci Google. Zwraca {"email", "nazwa", "pewny"}.

    "pewny" = Google jest dostawca tej skrzynki. Do istniejacego konta wpuszczamy
    tylko wtedy; inaczej konto Google zalozone na cudzy adres otwieraloby cudze sprawy.
    """
    import jwt
    if not czy_jwt(token):
        raise BladLogowania(_BLAD_GOOGLE)
    try:
        klucz = _weryfikator_google().get_signing_key_from_jwt(token)
        dane = jwt.decode(
            token, klucz.key, algorithms=["RS256"], audience=GOOGLE_KLIENT, leeway=30,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except Exception as blad:
        raise BladLogowania(_BLAD_GOOGLE) from blad
    if dane.get("iss") not in _GOOGLE_WYDAWCY:
        raise BladLogowania(_BLAD_GOOGLE)
    if time.time() - float(dane["iat"]) > _GOOGLE_MAKS_WIEK:
        raise BladLogowania("Logowanie przez Google wygaslo. Sprobuj ponownie.")
    email = str(dane.get("email") or "").strip().lower()
    if not email or dane.get("email_verified") not in (True, "true"):
        raise BladLogowania("Konto Google nie ma potwierdzonego adresu e-mail.")
    if not _jednorazowy(str(dane.get("jti") or f"{dane['sub']}.{dane['iat']}"), float(dane["exp"])):
        raise BladLogowania("Logowanie przez Google wygaslo. Sprobuj ponownie.")
    pewny = email.rsplit("@", 1)[-1] in _GOOGLE_DOMENY or bool(dane.get("hd"))
    return {"email": email, "nazwa": " ".join(str(dane.get("name") or "").split()), "pewny": pewny}


def dowod_logowania(email: str, teraz: float | None = None) -> str:
    """Odpowiedz na wyzwanie Cognito: czas i podpis HMAC. Te sama regule ma
    Lambda w infra/notarai-logowanie.yaml - zmieniaj obie naraz."""
    znacznik = str(int(time.time() if teraz is None else teraz))
    podpis = hmac.new(_GOOGLE_KLUCZ.encode(), f"{email.lower()}|{znacznik}".encode(),
                      hashlib.sha256).hexdigest()
    return f"{znacznik}.{podpis}"


def stan_konta(email: str) -> dict | None:
    """{"kancelaria", "stan", "aktywne"} albo None, gdy konta nie ma."""
    try:
        odp = _klient().admin_get_user(UserPoolId=PULA, Username=email)
    except Exception as blad:
        if type(blad).__name__ == "UserNotFoundException":
            return None
        raise
    atrybuty = {a["Name"]: a["Value"] for a in odp.get("UserAttributes") or []}
    return {"kancelaria": atrybuty.get("custom:kancelaria", ""),
            "stan": odp.get("UserStatus", ""), "aktywne": odp.get("Enabled", True)}


def _haslo_losowe(email: str) -> None:
    """Konto bez hasla znanego komukolwiek. Wlasne haslo mozna ustawic przez
    "Nie pamietam hasla"."""
    _klient().admin_set_user_password(
        UserPoolId=PULA, Username=email, Permanent=True,
        Password=secrets.token_urlsafe(32) + "aA1",
    )


def utworz_uzytkownika_bez_hasla(email: str, kancelaria: str) -> None:
    """Konto dla osoby wchodzacej przez Google: bez e-maila z haslem tymczasowym."""
    try:
        _klient().admin_create_user(
            UserPoolId=PULA,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "custom:kancelaria", "Value": kancelaria},
            ],
            MessageAction="SUPPRESS",
        )
    except Exception as blad:
        if type(blad).__name__ == "UsernameExistsException":
            raise BladLogowania("Konto o tym adresie juz istnieje.") from blad
        raise
    _haslo_losowe(email)
    log.info("utworzono konto uzytkownika (Google) w kancelarii %s", kancelaria)


def zaloguj_bez_hasla(email: str, stan: str = "") -> dict:
    """Sesja Cognito dla adresu potwierdzonego tokenem Google.

    Zaproszona osoba, ktora nie ustawila jeszcze hasla, dostaje haslo losowe:
    konto z haslem tymczasowym nie konczy logowania wlasnym wyzwaniem.
    """
    if stan == "FORCE_CHANGE_PASSWORD":
        _haslo_losowe(email)
    try:
        odp = _klient().initiate_auth(
            ClientId=KLIENT, AuthFlow="CUSTOM_AUTH", AuthParameters={"USERNAME": email},
        )
        if odp.get("ChallengeName") != "CUSTOM_CHALLENGE":
            raise BladLogowania(_BLAD_GOOGLE)
        odp = _klient().respond_to_auth_challenge(
            ClientId=KLIENT, ChallengeName="CUSTOM_CHALLENGE", Session=odp["Session"],
            ChallengeResponses={
                "USERNAME": (odp.get("ChallengeParameters") or {}).get("USERNAME", email),
                "ANSWER": dowod_logowania(email),
            },
        )
    except BladLogowania:
        raise
    except Exception as blad:
        nazwa = type(blad).__name__
        if nazwa in ("NotAuthorizedException", "UserNotFoundException"):
            log.info("nieudane logowanie przez Google")
            raise BladLogowania(_BLAD_GOOGLE) from blad
        if nazwa == "TooManyRequestsException":
            raise BladLogowania("Za duzo prob. Odczekaj chwile.") from blad
        raise
    log.info("udane logowanie przez Google")
    return _wynik(odp)


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
