"""e-Doręczenia: uwierzytelnienie systemu (signedJWT, RFC 7523) - GOV-02.

Źródło: Instrukcja integracji EZD (INT v1.9.7, PROD 07.2025), rozdz. 4.
Klucz prywatny pochodzi z sejfu i jest przekazywany jako funkcja (nigdy z pliku
JSON/env w repozytorium); jeden certyfikat = jeden system = jedna kancelaria.
Domyślnie tylko INT; PROD wymaga produkcja=True i certyfikatu kwalifikowanego.
"""
import re
import threading
import time
import uuid

import httpx
import jwt

TOKEN_URL = {
    "int": "https://int-ow.edoreczenia.gov.pl/auth/realms/EDOR/protocol/openid-connect/token",
    "prod": "https://ow.edoreczenia.gov.pl/auth/realms/EDOR/protocol/openid-connect/token",
}
# Wartości `aud` dosłownie z instrukcji (http, nie https) - potwierdzić na INT.
AUDIENCE = {
    "int": "http://int-ow.edoreczenia.gov.pl/auth/realms/EDOR",
    "prod": "http://ow.edoreczenia.gov.pl/auth/realms/EDOR",
}
ZYCIE_JWT_S = 300
MARGINES_S = 20
_ADE = re.compile(r"^(?:ADE\.)?[A-Z]{2}:[A-Z]{2}-[A-Z0-9-]{10,40}$")
_SYS = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class BladUwierzytelnienia(RuntimeError):
    pass


class KlientTokenu:
    def __init__(self, ade, nazwa_systemu, klucz_pem, srodowisko=None, *,
                 produkcja=False, client=None, zegar=time.time):
        if srodowisko not in TOKEN_URL:
            raise ValueError("Adapter e-Doręczeń jest domyślnie wyłączony - wskaż środowisko (int/prod).")
        if srodowisko == "prod" and not produkcja:
            raise ValueError("PROD wymaga jawnej zgody (produkcja=True) i certyfikatu kwalifikowanego notariusza.")
        if not _ADE.match(ade or "") or not _SYS.match(nazwa_systemu or ""):
            raise ValueError("Niepoprawny adres do e-Doręczeń lub nazwa systemu.")
        if not callable(klucz_pem):
            raise ValueError("Klucz prywatny podaj jako funkcję z sejfu, nie jako wartość.")
        self._ade, self._sys, self._klucz = ade, nazwa_systemu, klucz_pem
        self._env, self._client, self._zegar = srodowisko, client or httpx.Client(), zegar
        self._token, self._wazny_do = None, 0.0
        self._blokada = threading.Lock()

    def __repr__(self):
        return f"KlientTokenu({self._env}, {self._sys})"

    def _asercja(self):
        t = int(self._zegar())
        podmiot = f"{self._ade}.SYSTEM.{self._sys}"
        return jwt.encode({"aud": AUDIENCE[self._env], "iss": podmiot, "sub": podmiot,
                           "iat": t, "nbf": t, "exp": t + ZYCIE_JWT_S, "jti": str(uuid.uuid4())},
                          self._klucz(), algorithm="RS256", headers={"typ": "JWT"})

    def token(self):
        """Zwraca ważny token; NIE pobiera nowego, dopóki poprzedni jest ważny."""
        with self._blokada:
            if self._token and self._zegar() < self._wazny_do - MARGINES_S:
                return self._token
            try:
                r = self._client.post(
                    TOKEN_URL[self._env], params={"login_hint": self._ade},
                    data={"client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                          "grant_type": "client_credentials", "client_assertion": self._asercja()},
                    headers={"Accept": "application/json"}, timeout=10, follow_redirects=False)
                d = r.json() if r.status_code == 200 else {}
            except (httpx.HTTPError, ValueError, jwt.PyJWTError):
                raise BladUwierzytelnienia("Nie udało się uzyskać tokenu e-Doręczeń.") from None
            tok, ttl = d.get("access_token"), d.get("expires_in")
            if not isinstance(tok, str) or not isinstance(ttl, int) or ttl <= 0 or d.get("token_type", "Bearer").lower() != "bearer":
                raise BladUwierzytelnienia("Serwer e-Doręczeń odmówił lub zwrócił niepoprawny token.")
            self._token, self._wazny_do = tok, self._zegar() + ttl
            return tok

    def naglowki(self):
        return {"Authorization": "Bearer " + self.token()}
