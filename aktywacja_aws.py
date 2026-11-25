"""Produkcyjne backendy aktywacji rejestrów: DynamoDB (statusy, challenge) i
Secrets Manager (klucze notariuszy). eu-central-1. Bez e-maili w kluczach i nazwach
zasobów - tylko skróty SHA-256. Wartości sekretów czyta wyłącznie kod aplikacji w
czasie działania (rola zadania), nigdy człowiek ani agent."""
import hashlib
import json
import os
import re

from aktywacja_rejestrow import Konflikt

REGION = os.getenv("AWS_REGION", "eu-central-1")
TABELA = os.getenv("NOTARAI_REJESTRY_TABELA", "notarai-rejestry")
PREFIKS_SEKRETU = "notarai/rejestry/"
KLUCZ_KMS = os.getenv("NOTARAI_REJESTRY_KMS", "alias/notarai-rejestry")


def _h(x):
    return hashlib.sha256(x.encode()).hexdigest()


def _osoba(k, e):
    return f"{_h(k)[:24]}#{_h(e.lower())[:24]}"


class DynamoMagazyn:
    def __init__(self, tabela=TABELA, klient=None, region=REGION):
        import boto3
        self._c = klient or boto3.client("dynamodb", region_name=region)
        self._t = tabela

    @staticmethod
    def _s(v): return {"S": v}

    # challenge: w bazie tylko skrót nonce; usunięcie warunkowe = atomowe zużycie
    def zapisz_challenge(self, n, dane):
        self._c.put_item(TableName=self._t, Item={
            "pk": self._s("CH#" + _h(n)), "sk": self._s("CH"), "dane": self._s(json.dumps(dane)),
            "wygasa": {"N": str(int(dane["do"]) + 3600)}})

    def zuzyj_challenge(self, n):
        try:
            r = self._c.delete_item(TableName=self._t, Key={"pk": self._s("CH#" + _h(n)), "sk": self._s("CH")},
                                    ConditionExpression="attribute_exists(pk)", ReturnValues="ALL_OLD")
        except self._c.exceptions.ConditionalCheckFailedException:
            return None
        return json.loads(r["Attributes"]["dane"]["S"])

    def _klucz(self, k, e, u):
        return {"pk": self._s("REK#" + _osoba(k, e)), "sk": self._s(u)}

    def czytaj(self, k, e, u):
        r = self._c.get_item(TableName=self._t, Key=self._klucz(k, e, u), ConsistentRead=True).get("Item")
        return (json.loads(r["dane"]["S"]), int(r["wersja"]["N"])) if r else (None, 0)

    def zapisz(self, k, e, u, rek, wersja):
        item = {**self._klucz(k, e, u), "dane": self._s(json.dumps(rek)), "wersja": {"N": str(wersja + 1)}}
        kw = ({"ConditionExpression": "attribute_not_exists(pk)"} if wersja == 0 else
              {"ConditionExpression": "wersja = :w", "ExpressionAttributeValues": {":w": {"N": str(wersja)}}})
        try:
            self._c.put_item(TableName=self._t, Item=item, **kw)
        except self._c.exceptions.ConditionalCheckFailedException:
            raise Konflikt() from None

    def tozsamosc_osoby(self, k, e):
        r = self._c.get_item(TableName=self._t, ConsistentRead=True,
                             Key={"pk": self._s("OSOBA#" + _osoba(k, e)), "sk": self._s("TOZ")}).get("Item")
        return r["t"]["S"] if r else None

    def zwiaz_tozsamosc(self, k, e, t):
        o = _osoba(k, e)
        war = "attribute_not_exists(pk) OR {0} = :v"
        try:
            self._c.transact_write_items(TransactItems=[
                {"Put": {"TableName": self._t, "Item": {"pk": self._s("OSOBA#" + o), "sk": self._s("TOZ"), "t": self._s(t)},
                         "ConditionExpression": war.format("t"), "ExpressionAttributeValues": {":v": self._s(t)}}},
                {"Put": {"TableName": self._t, "Item": {"pk": self._s("TOZ#" + t), "sk": self._s("TOZ"), "o": self._s(o)},
                         "ConditionExpression": war.format("o"), "ExpressionAttributeValues": {":v": self._s(o)}}}])
            return True
        except self._c.exceptions.TransactionCanceledException:
            return False


    def krn_potwierdz(self, t, czynny=True):
        self._c.put_item(TableName=self._t, Item={"pk": self._s("KRN#" + t), "sk": self._s("KRN"),
                                                  "czynny": {"BOOL": bool(czynny)}})

    def krn_czy(self, t):
        r = self._c.get_item(TableName=self._t, ConsistentRead=True,
                             Key={"pk": self._s("KRN#" + t), "sk": self._s("KRN")}).get("Item")
        return bool(r and r["czynny"]["BOOL"])


class SejfSecretsManager:
    """Klucze per notariusz per usługa. `ma_klucz` nie czyta wartości (describe)."""
    def __init__(self, klient=None, region=REGION, kms=KLUCZ_KMS):
        import boto3
        self._c = klient or boto3.client("secretsmanager", region_name=region)
        self._kms = kms

    @staticmethod
    def nazwa(k, e, u):
        if not re.fullmatch(r"[a-z0-9_]{2,32}", u):
            raise ValueError("Niepoprawna usługa.")
        return f"{PREFIKS_SEKRETU}{_h(k)[:24]}/{_h(e.lower())[:24]}/{u}"

    def ma_klucz(self, k, e, u):
        try:
            d = self._c.describe_secret(SecretId=self.nazwa(k, e, u))
        except self._c.exceptions.ResourceNotFoundException:
            return False
        return "DeletedDate" not in d

    def zapisz_klucz(self, k, e, u, wartosc):
        """Wywoływane tylko ze ścieżki, w której notariusz sam wgrywa swój klucz."""
        n = self.nazwa(k, e, u)
        try:
            self._c.put_secret_value(SecretId=n, SecretString=wartosc)
        except self._c.exceptions.ResourceNotFoundException:
            self._c.create_secret(Name=n, SecretString=wartosc, KmsKeyId=self._kms,
                                  Tags=[{"Key": "projekt", "Value": "notarai"}])

    def klucz(self, k, e, u):
        """Tylko dla adaptera chronionego, po pozytywnej bramce `moze_uzyc`."""
        return self._c.get_secret_value(SecretId=self.nazwa(k, e, u))["SecretString"]

    def usun_klucz(self, k, e, u):
        self._c.delete_secret(SecretId=self.nazwa(k, e, u), RecoveryWindowInDays=7)
