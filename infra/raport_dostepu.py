"""notarai - raport dostepu do tresci spraw (dowod z sladu CloudTrail).

Co raport wykazuje, a czego nie
-------------------------------
Tresc spraw lezy w buckecie, ktorego polityka odmawia odczytu kazdemu poza
rola aplikacji i rola kopii zapasowej (infra/notarai-s3.yaml) - takze
administratorom konta. Czlowiek moze sie do tresci dostac tylko wtedy, gdy
ktos najpierw otworzy mu droge: zmieni zabezpieczenia bucketa, wejdzie do
dzialajacego kontenera, przyjmie role aplikacji, zmieni te role albo odtworzy
kopie zapasowa. Kazda z tych operacji zostawia wpis w sladzie CloudTrail,
a pliki sladu sa podpisywane przez AWS (kontrola integralnosci).

Raport czyta slad z wybranego okresu, sprawdza jego podpisy i wypisuje kazda
taka operacje. Wynik "brak operacji" znaczy: w okresie objetym nienaruszonym
sladem nikt nie otworzyl czlowiekowi drogi do tresci spraw.

Dostep serwisowy (administrator wchodzi do spraw kancelarii, gdy jej
wlasciciel sam to wlaczy) idzie przez aplikacje, wiec nie ma go w sladzie
CloudTrail. Aplikacja zapisuje kazde takie zdarzenie w dzienniku spietym
skrotami (dziennik_serwisu.py) i zostawia swiadka w logach CloudWatch, ktorych
nie da sie edytowac. Raport czyta swiadkow z okresu, sprawdza ciaglosc
lancucha i wypisuje kazde wlaczenie, wejscie i odwolanie. Logi aplikacji sa
trzymane 90 dni - raport trzeba sporzadzac co najmniej raz na kwartal.

Raport NIE dowodzi, ze "zaden czlowiek nigdy nie widzial danych": nie obejmuje
osob w kancelarii, okresu sprzed zalozenia sladu, pracownikow AWS ani kodu
samej aplikacji (kazde wdrozenie jest wypisane osobno, z obrazem).

Uzycie (z katalogu notarai, profil z prawem odczytu bucketa sladu):
    py -3 infra/raport_dostepu.py --od 2026-11-15 --do 2026-12-15 --wynik raport.json
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

BUCKET_SPRAW = "notarai-sprawy"
ROLE_Z_DOSTEPEM = ("notarai-ecs-zadanie", "notarai-kopia")
SLAD = "notarai-slad"
LOGI_APLIKACJI = "/ecs/notarai"

# Zmiana tej listy = zmiana regul w infra/notarai-nadzor.yaml.
ZABEZPIECZENIA_BUCKETA = {
    "PutBucketPolicy", "DeleteBucketPolicy", "PutBucketAcl", "PutBucketPublicAccessBlock",
    "DeleteBucketPublicAccessBlock", "PutBucketReplication", "DeleteBucket",
}
ZMIANY_ROLI = {
    "UpdateAssumeRolePolicy", "AttachRolePolicy", "DetachRolePolicy", "PutRolePolicy",
    "DeleteRolePolicy", "PutRolePermissionsBoundary", "DeleteRolePermissionsBoundary",
}
ZMIANY_SLADU = {"StopLogging", "DeleteTrail", "UpdateTrail", "PutEventSelectors",
                "PutInsightSelectors"}
ODTWORZENIA = {"StartRestoreJob", "StartCopyJob"}
# Kazde uruchomienie kodu z rola aplikacji - takze jednorazowe zadanie poza usluga.
WDROZENIA = {"RegisterTaskDefinition", "UpdateService", "CreateService", "RunTask", "StartTask"}
# Wlaczenie zapisu zapytan do modelu skierowaloby tresc skanow do logow.
ZAPIS_ZAPYTAN_MODELU = {"PutModelInvocationLoggingConfiguration"}
# Usuniecie logow aplikacji usuneloby swiadkow dostepu serwisowego.
ZMIANY_LOGOW = {"DeleteLogGroup", "DeleteLogStream", "PutRetentionPolicy", "DeleteRetentionPolicy"}


def klasyfikuj(z: dict) -> str | None:
    """Rodzaj zdarzenia, ktore otwiera droge do tresci spraw - albo None.

    "wdrozenie" nie otwiera drogi samo w sobie; wypisujemy je, bo zmienia kod,
    ktory czyta sprawy.
    """
    nazwa = z.get("eventName", "")
    zrodlo = z.get("eventSource", "")
    parametry = z.get("requestParameters") or {}
    kto = z.get("userIdentity") or {}
    if z.get("errorCode"):
        return None            # operacja odrzucona - droga nie zostala otwarta
    if zrodlo == "s3.amazonaws.com" and nazwa in ZABEZPIECZENIA_BUCKETA:
        return "zabezpieczenia_bucketa" if parametry.get("bucketName") == BUCKET_SPRAW else None
    if zrodlo == "ecs.amazonaws.com" and nazwa == "ExecuteCommand":
        return "wejscie_do_kontenera"
    if zrodlo == "iam.amazonaws.com" and nazwa in ZMIANY_ROLI:
        return "zmiana_roli" if parametry.get("roleName") in ROLE_Z_DOSTEPEM else None
    if zrodlo == "sts.amazonaws.com" and nazwa.startswith("AssumeRole"):
        rola = str(parametry.get("roleArn", "")).rsplit("/", 1)[-1]
        if rola not in ROLE_Z_DOSTEPEM:
            return None
        usluga = kto.get("invokedBy", "") if kto.get("type") == "AWSService" else ""
        dozwolona = {"notarai-ecs-zadanie": "ecs-tasks.amazonaws.com",
                     "notarai-kopia": "backup.amazonaws.com"}[rola]
        return None if usluga == dozwolona else "przyjecie_roli"
    if zrodlo == "cloudtrail.amazonaws.com" and nazwa in ZMIANY_SLADU:
        return "zmiana_sladu"
    if zrodlo == "logs.amazonaws.com" and nazwa in ZMIANY_LOGOW:
        return "zmiana_logow_aplikacji" if parametry.get("logGroupName") == LOGI_APLIKACJI else None
    if zrodlo == "bedrock.amazonaws.com" and nazwa in ZAPIS_ZAPYTAN_MODELU:
        return "zapis_zapytan_modelu"
    if zrodlo == "backup.amazonaws.com" and nazwa in ODTWORZENIA:
        return "odtworzenie_kopii"
    if zrodlo == "ecs.amazonaws.com" and nazwa in WDROZENIA:
        return "wdrozenie"
    return None


def opis(z: dict, rodzaj: str) -> dict:
    """Wpis do raportu: bez adresow IP i bez parametrow, ktore moglyby niesc dane."""
    kto = z.get("userIdentity") or {}
    wpis = {"czas": z.get("eventTime"), "rodzaj": rodzaj, "operacja": z.get("eventName"),
            "region": z.get("awsRegion"), "identyfikator": z.get("eventID"),
            "kto": kto.get("arn") or kto.get("invokedBy") or kto.get("type")}
    if rodzaj == "wdrozenie":
        definicja = (z.get("requestParameters") or {})
        obrazy = [k.get("image") for k in definicja.get("containerDefinitions") or []]
        wpis["obraz"] = obrazy or definicja.get("taskDefinition")
    return wpis


def zbierz(zdarzenia) -> tuple[list[dict], list[dict], int]:
    otwarcia, wdrozenia, razem = [], [], 0
    for z in zdarzenia:
        razem += 1
        rodzaj = klasyfikuj(z)
        if rodzaj == "wdrozenie":
            wdrozenia.append(opis(z, rodzaj))
        elif rodzaj:
            otwarcia.append(opis(z, rodzaj))
    klucz = lambda w: w["czas"] or ""  # noqa: E731
    return sorted(otwarcia, key=klucz), sorted(wdrozenia, key=klucz), razem


# --- dostep serwisowy: swiadkowie w logach aplikacji ---------------------------

_SWIADEK = re.compile(r"serwis-dziennik nr=(\d+) rodzaj=(\w+) kancelaria=(\S+) "
                      r"skrot=([a-p]{64}) poprzedni=([a-p]{64})")
_NA_CYFRY = str.maketrans("ghijklmnop", "0123456789")


def swiadek(wiadomosc: str) -> dict | None:
    """Wpis dziennika serwisu odczytany z wiersza logu aplikacji albo None."""
    m = _SWIADEK.search(wiadomosc)
    if not m:
        return None
    return {"nr": int(m.group(1)), "rodzaj": m.group(2), "kancelaria": m.group(3),
            "skrot": m.group(4).translate(_NA_CYFRY), "poprzedni": m.group(5).translate(_NA_CYFRY)}


def sprawdz_swiadkow(lista: list[dict]) -> dict:
    """Czy swiadkowie z okresu tworza nieprzerwany lancuch: numery po kolei,
    kazdy wskazuje skrot poprzedniego. Brak numeru albo zerwane ogniwo znaczy,
    ze jakis wpis usunieto albo zmieniono."""
    wg_nr: dict[int, dict] = {}
    bledy = []
    for w in lista:
        if w["nr"] in wg_nr and wg_nr[w["nr"]]["skrot"] != w["skrot"]:
            bledy.append(f"wpis {w['nr']}: dwa rozne skroty")
        wg_nr.setdefault(w["nr"], w)
    kolejne = [wg_nr[n] for n in sorted(wg_nr)]
    for a, b in zip(kolejne, kolejne[1:]):
        if b["nr"] != a["nr"] + 1:
            bledy.append(f"brak wpisow miedzy {a['nr']} a {b['nr']}")
        elif b["poprzedni"] != a["skrot"]:
            bledy.append(f"wpis {b['nr']}: nie wskazuje wpisu {a['nr']}")
    return {"lancuch_ciagly": not bledy, "bledy": bledy, "wpisy": kolejne}


def swiadkowie_z_logow(logi, od: date, do: date) -> list[dict]:
    poczatek = int(datetime(od.year, od.month, od.day, tzinfo=timezone.utc).timestamp() * 1000)
    koniec = int((datetime(do.year, do.month, do.day, tzinfo=timezone.utc)
                  + timedelta(days=1)).timestamp() * 1000)
    wynik = []
    for strona in logi.get_paginator("filter_log_events").paginate(
            logGroupName=LOGI_APLIKACJI, filterPattern='"serwis-dziennik"',
            startTime=poczatek, endTime=koniec):
        for zdarzenie in strona.get("events", []):
            w = swiadek(zdarzenie.get("message", ""))
            if w:
                czas = datetime.fromtimestamp(zdarzenie["timestamp"] / 1000, tz=timezone.utc)
                wynik.append({"czas": czas.isoformat(timespec="seconds"), **w})
    return wynik


def _dni(od: date, do: date):
    while od <= do:
        yield od
        od += timedelta(days=1)


def zdarzenia_ze_sladu(s3, bucket: str, konto: str, od: date, do: date):
    """Wszystkie zdarzenia ze wszystkich regionow w okresie (pliki sladu z S3)."""
    korzen = f"AWSLogs/{konto}/CloudTrail/"
    regiony = [p["Prefix"] for p in s3.list_objects_v2(
        Bucket=bucket, Prefix=korzen, Delimiter="/").get("CommonPrefixes", [])]
    strony = s3.get_paginator("list_objects_v2")
    for region in regiony:
        for dzien in _dni(od, do):
            prefiks = f"{region}{dzien:%Y/%m/%d}/"
            for strona in strony.paginate(Bucket=bucket, Prefix=prefiks):
                for obiekt in strona.get("Contents", []):
                    tresc = s3.get_object(Bucket=bucket, Key=obiekt["Key"])["Body"].read()
                    yield from json.loads(gzip.decompress(tresc)).get("Records", [])


def sprawdz_podpisy(slad_arn: str, od: date, do: date, region: str) -> dict:
    """Kontrola integralnosci sladu narzedziem AWS (podpisy plikow skrotow)."""
    wynik = subprocess.run(
        ["aws", "cloudtrail", "validate-logs", "--trail-arn", slad_arn, "--region", region,
         "--start-time", f"{od:%Y-%m-%d}T00:00:00Z", "--end-time", f"{do:%Y-%m-%d}T23:59:59Z"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    tekst = (wynik.stdout + wynik.stderr).strip()
    wiersze = [w.strip() for w in tekst.splitlines() if "valid" in w.lower() or "INVALID" in w]
    return {"nienaruszony": wynik.returncode == 0 and "INVALID" not in tekst
            and any("valid" in w for w in wiersze),
            "wynik_narzedzia": wiersze[-6:]}


def stan_polityki(s3) -> dict:
    """Czy bucket spraw ma dzis zakaz odczytu dla wszystkich poza rolami uslugi."""
    try:
        polityka = json.loads(s3.get_bucket_policy(Bucket=BUCKET_SPRAW)["Policy"])
    except Exception as blad:  # noqa: BLE001
        return {"zakaz_obowiazuje": False, "powod": type(blad).__name__}
    zakazy = {}
    for st in polityka.get("Statement", []):
        if st.get("Effect") != "Deny" or st.get("Principal") not in ("*", {"AWS": "*"}):
            continue
        wyjatki = ((st.get("Condition") or {}).get("ArnNotLike") or {}).get("aws:PrincipalArn") or []
        wyjatki = [wyjatki] if isinstance(wyjatki, str) else wyjatki
        zakazy[st.get("Sid")] = sorted(a.rsplit("/", 1)[-1] for a in wyjatki)
    oczekiwane = sorted(ROLE_Z_DOSTEPEM)
    ok = all(zakazy.get(sid) == oczekiwane
             for sid in ("TrescSprawTylkoDlaAplikacji", "SpisPlikowTylkoDlaAplikacji"))
    return {"zakaz_obowiazuje": ok, "wyjatki": zakazy}


def raport(od: date, do: date, region: str = "eu-central-1") -> dict:
    import boto3
    sesja = boto3.Session(region_name=region)
    konto = sesja.client("sts").get_caller_identity()["Account"]
    slad = sesja.client("cloudtrail").describe_trails(trailNameList=[SLAD])["trailList"][0]
    s3 = sesja.client("s3")
    otwarcia, wdrozenia, razem = zbierz(
        zdarzenia_ze_sladu(s3, slad["S3BucketName"], konto, od, do))
    podpisy = sprawdz_podpisy(slad["TrailARN"], od, do, region)
    serwis = sprawdz_swiadkow(swiadkowie_z_logow(sesja.client("logs"), od, do))
    tresc = {
        "schemat": "notarai.raport-dostepu.v1",
        "okres": {"od": f"{od:%Y-%m-%d}", "do": f"{do:%Y-%m-%d}"},
        "sporzadzono": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "slad": {"arn": slad["TrailARN"], "wszystkie_regiony": slad.get("IsMultiRegionTrail"),
                 "kontrola_integralnosci": slad.get("LogFileValidationEnabled"), **podpisy},
        "polityka_bucketa_dzis": stan_polityki(s3),
        "przejrzano_zdarzen": razem,
        "operacje_otwierajace_droge": otwarcia,
        "wdrozenia_aplikacji": wdrozenia,
        "dostep_serwisowy": {
            "opis": "Wejscia administratora do spraw kancelarii, wlaczone przez jej wlasciciela.",
            "lancuch_ciagly": serwis["lancuch_ciagly"], "bledy": serwis["bledy"],
            "zdarzenia": serwis["wpisy"],
            "wejsc_administratora": sum(1 for w in serwis["wpisy"] if w["rodzaj"] == "wejscie"),
        },
        "zakres": ("Operacje administracyjne na koncie AWS w okresie objetym sladem oraz dostep "
                   "serwisowy przez aplikacje. Poza zakresem: osoby w kancelarii, pracownicy "
                   "dostawcy chmury, kod aplikacji, okres sprzed zalozenia sladu i dziennika."),
    }
    # BRAK_OPERACJI: nikt nie otworzyl drogi poza aplikacja. Dostep serwisowy
    # jest wypisany osobno - to droga otwierana przez sama kancelarie.
    tresc["wniosek"] = (
        "SA_OPERACJE" if otwarcia
        else "BRAK_OPERACJI" if podpisy["nienaruszony"] and razem and serwis["lancuch_ciagly"]
        and tresc["polityka_bucketa_dzis"]["zakaz_obowiazuje"]
        else "NIEZWERYFIKOWANY")
    kanon = json.dumps(tresc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**tresc, "sha256": hashlib.sha256(kanon.encode("utf-8")).hexdigest()}


def main() -> int:
    dzis = datetime.now(timezone.utc).date()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--od", type=date.fromisoformat, default=dzis - timedelta(days=30))
    p.add_argument("--do", type=date.fromisoformat, default=dzis)
    p.add_argument("--wynik", default="")
    a = p.parse_args()
    wynik = raport(a.od, a.do)
    tekst = json.dumps(wynik, ensure_ascii=False, indent=2)
    if a.wynik:
        with open(a.wynik, "w", encoding="utf-8") as plik:
            plik.write(tekst)
    print(tekst)
    return 0 if wynik["wniosek"] == "BRAK_OPERACJI" else 1


if __name__ == "__main__":
    sys.exit(main())
