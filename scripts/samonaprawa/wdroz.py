"""Wdrozenie poprawki z potoku samonaprawy: ta sama sciezka co wdrozenie.yml,
ale z AWS (CodeBuild) przez boto3 i AWS CLI, bez GitHuba.

  1. zrodla uruchomionej wersji (paczka zrodla-<TAG>.zip, jak ja wysyla wdrozenie.yml),
  2. obraz: paczka zrodel -> projekt CodeBuild z stosu notarai-budowanie,
  3. aws cloudformation deploy stosu notarai-aplikacja (rola notarai-cloudformation),
  4. ecs services-stable, sprawdzenie obrazu, smoke test produkcji,
  5. cofniecie = to samo wdrozenie z poprzednim tagiem (obraz jest w ECR).

Wszystkie wywolania zewnetrzne ida przez klientow wstrzykiwanych w konstruktorze,
wiec potok da sie przetestowac bez sieci.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

REGION = "eu-central-1"
KONTO = "127621462971"
STOS_APLIKACJI = "notarai-aplikacja"
STOS_BUDOWANIA = "notarai-budowanie"
KLASTER = "notarai"
USLUGA = "notarai"
ROLA_CLOUDFORMATION = f"arn:aws:iam::{KONTO}:role/notarai-cloudformation"
SEKRET_TOKENU = "notarai/samonaprawa-github"
GRUPA_LOGOW_BUDOWANIA = "/aws/codebuild/notarai-obraz"


class BladWdrozenia(RuntimeError):
    pass


def tag_z_obrazu(obraz: str) -> str:
    return obraz.rsplit(":", 1)[-1] if ":" in obraz.rsplit("/", 1)[-1] else ""


class Wdrozenie:
    def __init__(self, region: str = REGION, klienci: dict | None = None, uruchom=None, spij=time.sleep,
                 teraz=time.time) -> None:
        self.region = region
        self._klienci = dict(klienci or {})
        self._uruchom = uruchom or subprocess.run
        self._spij = spij
        self._teraz = teraz

    def _k(self, nazwa: str):
        if nazwa not in self._klienci:
            import boto3
            self._klienci[nazwa] = boto3.client(nazwa, region_name=self.region)
        return self._klienci[nazwa]

    # ------------------------------------------------------------ odczyty
    def wyjscie_stosu(self, stos: str, klucz: str) -> str:
        odp = self._k("cloudformation").describe_stacks(StackName=stos)
        for w in odp["Stacks"][0].get("Outputs", []):
            if w["OutputKey"] == klucz:
                return w["OutputValue"]
        raise BladWdrozenia(f"stos {stos} nie ma wyjscia {klucz}")

    def stos_aplikacji(self) -> dict:
        return self._k("cloudformation").describe_stacks(StackName=STOS_APLIKACJI)["Stacks"][0]

    def parametry_stosu(self) -> dict[str, str]:
        return {p["ParameterKey"]: p.get("ParameterValue", "") for p in self.stos_aplikacji().get("Parameters", [])}

    def tag_stosu(self) -> str:
        """Tag z parametrow stosu - to od niego cofamy."""
        return self.parametry_stosu().get("TagObrazu", "")

    def obraz_uslugi(self) -> str:
        ecs = self._k("ecs")
        usluga = ecs.describe_services(cluster=KLASTER, services=[USLUGA])["services"][0]
        definicja = ecs.describe_task_definition(taskDefinition=usluga["taskDefinition"])["taskDefinition"]
        return definicja["containerDefinitions"][0]["image"]

    def aktualny_tag(self) -> str:
        """Tag obrazu uruchomionego w produkcji (z definicji zadania uslugi ECS)."""
        return tag_z_obrazu(self.obraz_uslugi())

    def czekaj_na_stos(self, minut: int = 75) -> bool:
        """Czeka, az stos aplikacji przestanie byc *_IN_PROGRESS (zwykle wdrozenie trwa)."""
        koniec = self._teraz() + minut * 60
        while True:
            if not self.stos_aplikacji()["StackStatus"].endswith("_IN_PROGRESS"):
                return True
            if self._teraz() >= koniec:
                return False
            self._spij(30)

    # ------------------------------------------------------------ zrodla i obraz
    def bucket_zrodel(self) -> str:
        return self.wyjscie_stosu(STOS_BUDOWANIA, "BucketZrodel")

    def klucz_zrodel(self, tag: str) -> str:
        return f"notarai/zrodla-{tag}.zip"

    def pobierz_zrodla(self, tag: str, cel: Path, bucket_wlasny: str = "") -> str:
        """Paczka zrodel wersji z produkcji. Najpierw bucket budowania, potem kopia
        w buckecie samonaprawy (paczki budowania wygasaja). Zwraca nazwe zrodla."""
        s3 = self._k("s3")
        miejsca = [(self.bucket_zrodel(), self.klucz_zrodel(tag))]
        if bucket_wlasny:
            miejsca.append((bucket_wlasny, f"zrodla/{tag}.zip"))
        for bucket, klucz in miejsca:
            try:
                s3.download_file(bucket, klucz, str(cel))
                return f"s3://{bucket}/{klucz}"
            except Exception as e:  # noqa: BLE001 - brak klucza to ClientError 404/403
                ostatni = type(e).__name__
        raise BladWdrozenia(f"brak paczki zrodel wersji {tag} w S3 ({ostatni}). Paczki budowania wygasaja; "
                            "zrob zwykle wdrozenie (workflow wdrozenie.yml), a potem ponow zgloszenie.")

    def wyslij_zrodla(self, tag: str, zip_sciezka: Path, bucket_wlasny: str = "") -> tuple[str, str]:
        bucket, klucz = self.bucket_zrodel(), self.klucz_zrodel(tag)
        s3 = self._k("s3")
        s3.upload_file(str(zip_sciezka), bucket, klucz)
        if bucket_wlasny:
            s3.upload_file(str(zip_sciezka), bucket_wlasny, f"zrodla/{tag}.zip")
        return bucket, klucz

    def obraz_istnieje(self, tag: str) -> bool:
        repo = self.wyjscie_stosu(STOS_BUDOWANIA, "RepozytoriumUri").split("/", 1)[1]
        try:
            self._k("ecr").describe_images(repositoryName=repo, imageIds=[{"imageTag": tag}])
            return True
        except Exception as e:  # noqa: BLE001
            if type(e).__name__ == "ImageNotFoundException" or "ImageNotFound" in str(e):
                return False
            raise

    def zbuduj_obraz(self, tag: str, zip_sciezka: Path, bucket_wlasny: str = "", limit_minut: int = 30) -> None:
        if self.obraz_istnieje(tag):
            return
        bucket, klucz = self.wyslij_zrodla(tag, zip_sciezka, bucket_wlasny)
        cb = self._k("codebuild")
        projekt = self.wyjscie_stosu(STOS_BUDOWANIA, "ProjektBudowania")
        id_budowy = cb.start_build(
            projectName=projekt, sourceLocationOverride=f"{bucket}/{klucz}",
            environmentVariablesOverride=[{"name": "IMAGE_TAG", "value": tag, "type": "PLAINTEXT"}])["build"]["id"]
        koniec = self._teraz() + limit_minut * 60
        while True:
            self._spij(20)
            budowa = cb.batch_get_builds(ids=[id_budowy])["builds"][0]
            if budowa["buildStatus"] != "IN_PROGRESS":
                break
            if self._teraz() > koniec:
                raise BladWdrozenia(f"budowanie obrazu {tag} trwa dluzej niz {limit_minut} min")
        if budowa["buildStatus"] != "SUCCEEDED":
            raise BladWdrozenia(f"budowanie obrazu {tag} zakonczone statusem {budowa['buildStatus']}")

    # ------------------------------------------------------------ wdrozenie stosu
    def parametry_wdrozenia(self, tag: str) -> list[str]:
        """Te same nadpisania co wdrozenie.yml; rozmiar bierzemy z biezacego stosu."""
        biezace = self.parametry_stosu()
        email = biezace.get("EmailAlarmowy", "")
        if not email or email == "None":
            admini = biezace.get("Administratorzy", "")
            email = admini.replace(",", "\n").split("\n")[0].replace(" ", "") if admini else ""
        wynik = [f"TagObrazu={tag}", "Tokenomia=true"]
        if email and email != "None":
            wynik.append(f"EmailAlarmowy={email}")
        sekret = biezace.get("SamonaprawaSekretArn", "")
        if not sekret:
            try:
                sekret = self._k("secretsmanager").describe_secret(SecretId=SEKRET_TOKENU).get("ARN", "")
            except Exception:  # noqa: BLE001 - sekretu moze nie byc
                sekret = ""
        if sekret:
            wynik.append(f"SamonaprawaSekretArn={sekret}")
        for klucz, domyslna in (("Cpu", "512"), ("Pamiec", "2048"), ("LiczbaKopii", "1")):
            wynik.append(f"{klucz}={biezace.get(klucz) or domyslna}")
        return wynik

    def aktualizuj_stos(self, tag: str, szablon: Path) -> None:
        polecenie = ["aws", "cloudformation", "deploy", "--stack-name", STOS_APLIKACJI,
                     "--template-file", str(szablon), "--role-arn", ROLA_CLOUDFORMATION,
                     "--capabilities", "CAPABILITY_NAMED_IAM", "--tags", "projekt=notarai",
                     "--no-fail-on-empty-changeset", "--region", self.region,
                     "--parameter-overrides", *self.parametry_wdrozenia(tag)]
        wynik = self._uruchom(polecenie, capture_output=True, text=True)
        if wynik.returncode != 0:
            raise BladWdrozenia(f"aws cloudformation deploy: kod {wynik.returncode}: {(wynik.stderr or '')[-800:]}")

    def czekaj_stabilny(self) -> None:
        self._k("ecs").get_waiter("services_stable").wait(
            cluster=KLASTER, services=[USLUGA], WaiterConfig={"Delay": 15, "MaxAttempts": 80})

    def smoke(self, drzewo: Path) -> bool:
        wynik = self._uruchom(["python3", "scripts/smoke_public_demo.py"], cwd=str(drzewo),
                              capture_output=True, text=True, timeout=600)
        return wynik.returncode == 0

    def wdroz(self, tag: str, szablon: Path, drzewo: Path) -> dict:
        """Aktualizacja stosu + kontrola. {"wynik": "success"|"blad"|"wyprzedzone", "powod": str, "koniec_ms": int}

        "wyprzedzone": w trakcie ktos wdrozyl inny tag - nie cofamy w ciemno.
        """
        repo = self.wyjscie_stosu(STOS_BUDOWANIA, "RepozytoriumUri")
        try:
            self.aktualizuj_stos(tag, szablon)
            self.czekaj_stabilny()
        except Exception as e:  # noqa: BLE001
            return {"wynik": "blad", "powod": f"wdrozenie stosu: {str(e)[:300]}", "koniec_ms": int(self._teraz() * 1000)}
        koniec_ms = int(self._teraz() * 1000)
        obraz = self.obraz_uslugi()
        if obraz != f"{repo}:{tag}":
            if self.tag_stosu() != tag:
                return {"wynik": "wyprzedzone", "powod": f"ECS uzywa {obraz}; ktos wdrozyl inna wersje",
                        "koniec_ms": koniec_ms}
            return {"wynik": "blad", "powod": f"ECS uzywa obrazu {obraz}, oczekiwano {repo}:{tag}",
                    "koniec_ms": koniec_ms}
        if not self.smoke(drzewo):
            return {"wynik": "blad", "powod": "smoke test produkcji nie przeszedl", "koniec_ms": koniec_ms}
        return {"wynik": "success", "powod": "", "koniec_ms": koniec_ms}
