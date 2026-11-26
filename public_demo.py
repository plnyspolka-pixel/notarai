"""Public demo capability: synthetic data only, never production authorization.

This deliberately public token is not a Cognito identity, helper token or
administrator credential. The auth middleware intercepts it before ANY
public-route exceptions. Demo requests never reach application handlers,
tenant storage, billing, AWS AI, or integrations.
"""
import json
import os
from datetime import date, timedelta
from fastapi.responses import JSONResponse

TOKEN = "notarai-public-demo-v1"
HELPER_TOKEN = "pom_demo_public_v1"
TENANT = "notarai-demo-public"
CASE = "DEMO001"


def enabled():
    return os.getenv("NOTARAI_PUBLIC_DEMO", "1") == "1"


def is_demo(token):
    return token == TOKEN


def is_demo_helper(token):
    return token == HELPER_TOKEN


def response(data, status=200):
    return JSONResponse(data, status_code=status,
                        headers={"Cache-Control": "no-store"})


def case_summary():
    return {"id": CASE, "nazwa": "DEMO — sprzedaż mieszkania",
            "sygnatura": "DEMO/1", "utworzono": date.today().isoformat(),
            "wzor": "Umowa demonstracyjna", "skany": 0, "stron": 0,
            "etap": 3, "sprawdzenia": 0}


def case_detail():
    return {**case_summary(), "polecenie": "Przykładowy projekt sprzedaży lokalu.",
            "skany": [], "warianty": 0, "pola": [], "braki": [],
            "rozbieznosci": [], "rozmowa": [],
            "projekt": "DEMO – FIKCYJNY PROJEKT. Strony demonstracyjne uzgadniają sprzedaż przykładowego lokalu. Nie jest to akt notarialny.",
            "brakujace": 0, "do_wyboru": 0, "plik": None, "nazwa_pliku": None,
            "wysilek": "", "sprawdzenia": [], "zgodnosc": None,
            "projekt_stan": {}}


async def handle(request):
    if not enabled():
        return response({"detail": "Tryb demo jest wyłączony."}, 403)
    if request.headers.get("x-serwis-kancelaria"):
        return response({"detail": "Demo nie ma dostępu serwisowego."}, 403)
    path, method = request.url.path, request.method
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    # The public demo can pair the extension, but its helper token exposes only
    # an empty queue and disconnect. All page automation remains disabled.
    if token == HELPER_TOKEN:
        if method == "GET" and path == "/api/pomocnik/zlecenia":
            return response([])
        if method == "POST" and path == "/api/pomocnik/odlacz":
            return response({"odlaczono": True})
        return response({"detail": "Ta czynność nie jest dostępna w publicznym demo."}, 403)
    if method == "POST" and path == "/api/urzadzenia/rozszerzenie":
        if token != TOKEN:
            return response({"detail": "Zaloguj się do demo."}, 401)
        return response({"token": HELPER_TOKEN, "tozsamosc": "demo"})
    # Static responses only; no application handler, network, storage or model.
    if method == "GET":
        fixtures = {
            "/api/ustawienia": {"przechowywanie": "chmura", "sterowanie_przegladarka": False,
                "pomocnik_polaczony": False, "ekw": False, "transkrypcja": False,
                "ogolne": {}, "demo": True, "kancelaria": TENANT},
            "/api/ustawienia/ogolne": {},
            "/api/sprawy": [case_summary()],
            "/api/sprawy/" + CASE: case_detail(),
            "/api/sprawy/" + CASE + "/pliki": [],
            "/api/sprawy/" + CASE + "/sprawdzenia": [],
            "/api/sprawy/" + CASE + "/ksiegi": [],
            "/api/kalendarz": [{"id": "demo-1", "data": (date.today()+timedelta(days=1)).isoformat(),
                "godzina": "11:30", "koniec": "12:30", "rodzaj": "Sprzedaż lokalu (DEMO)",
                "uczestnicy": "Fikcyjny klient", "sprawa": CASE, "uwagi": "Dane demonstracyjne",
                "telefony": []}],
            "/api/kalendarz/dni": {},
            "/api/osoby": [],
            "/api/kredyty": {"egzekwowana": False, "saldo": 0, "moge_kupic": False,
                "platnosci_wlaczone": False},
            "/api/urzadzenia": {"dostepne": False, "polaczony": False, "urzadzenia": []},
            "/api/asystent-kancelarii/prosby": [],
            "/api/pulpit-ai/narzedzia": {"narzedzia": [], "glos": False},
        }
        if path in fixtures:
            return response(fixtures[path])
    if method == "POST" and path == "/api/pulpit-ai/rozmowa":
        # Bounded request body, deterministic simulation, never echo input.
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 8192:
                return response({"detail": "Polecenie demo jest za długie."}, 413)
            body.extend(chunk)
        try:
            data = json.loads(body)
            msg = data["wiadomosc"]
            if not isinstance(msg, str) or len(msg) > 2000:
                raise ValueError
        except (ValueError, TypeError, KeyError, UnicodeError):
            return response({"detail": "Nieprawidłowe polecenie demo."}, 400)
        msg = msg.lower()
        if any(word in msg for word in ("kalendarz", "termin", "wizyt")):
            result = {"odpowiedz": "DEMO: jutro o 11:30 zaplanowano fikcyjną sprzedaż lokalu.",
                      "akcje": [{"typ": "otworz", "ekran": "kalendarz"}]}
        elif any(word in msg for word in ("spraw", "projekt", "panel")):
            result = {"odpowiedz": "DEMO: dostępna jest przykładowa sprawa DEMO/1. Otwieram panel.",
                      "akcje": [{"typ": "otworz", "ekran": "panel"}]}
        else:
            result = {"odpowiedz": "To symulacja czatu NotarAI. Możesz otworzyć sprawy lub kalendarz. Prawdziwe operacje i model AI są wyłączone.", "akcje": []}
        return response(result)
    return response({"detail": "Ta czynność nie jest dostępna w publicznym demo."}, 403)
