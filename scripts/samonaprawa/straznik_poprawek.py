"""Straznik wdrozen z GitHuba: poprawka z produkcji nie moze zniknac przy zwyklym wdrozeniu.

Wywolywany w .github/workflows/wdrozenie.yml PRZED budowaniem obrazu (tylko stdlib + aws CLI):
  1. rejestr poprawek (tabela notarai-samonaprawa, rekordy NAPRAWA) - poprawki wdrozone
     przez potok AWS, ktorych jeszcze nie ma w master (status do_zsynchronizowania),
  2. dla kazdej, po kolei: patch z S3; `git apply --check --reverse` zdrowy = poprawka juz
     jest w tym kodzie (pomijamy); inaczej `git apply --3way` na wyewidencjonowanym HEAD,
  3. commit lokalny (bez pusha), z niego budowany jest obraz,
  4. tag obrazu: <sha12>-sn<skrot id poprawek>, inny niz zwykly.
Gdy poprawka sie nie stosuje: GLOSNA porazka (kod 1) i mail na notarai-alarmy. Nigdy nie
wdrazamy po cichu bez poprawki. Brak tabeli (stos samonaprawy niewdrozony) = brak poprawek.

Uzycie: python3 scripts/samonaprawa/straznik_poprawek.py --tag <sha12> [--zapisz-env $GITHUB_ENV]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REGION = "eu-central-1"
KONTO = "127621462971"
TABELA = "notarai-samonaprawa"
BUCKET = f"notarai-samonaprawa-{KONTO}-{REGION}"
TEMAT = f"arn:aws:sns:{REGION}:{KONTO}:notarai-alarmy"
DO_ZSYNCHRONIZOWANIA = "do_zsynchronizowania"


class BladStraznika(RuntimeError):
    pass


def _aws(uruchom, *argumenty: str, bajty: bool = False):
    wynik = uruchom(["aws", *argumenty, "--region", REGION], capture_output=True, text=not bajty)
    return wynik


def oczekujace(uruchom=subprocess.run) -> list[dict]:
    """Poprawki do_zsynchronizowania w kolejnosci wdrozenia (sk rosnaco)."""
    w = _aws(uruchom, "dynamodb", "query", "--table-name", TABELA, "--consistent-read",
             "--key-condition-expression", "pk = :p", "--expression-attribute-values",
             json.dumps({":p": {"S": "NAPRAWA"}}), "--output", "json")
    if w.returncode != 0:
        if "ResourceNotFoundException" in (w.stderr or ""):
            return []       # stos notarai-samonaprawa jeszcze nie wdrozony
        raise BladStraznika(f"nie moge odczytac rejestru poprawek: {(w.stderr or '')[-400:]}")
    wynik = []
    for wpis in json.loads(w.stdout or "{}").get("Items", []):
        p = {k: next(iter(v.values())) for k, v in wpis.items() if isinstance(v, dict) and len(v) == 1}
        if p.get("status") == DO_ZSYNCHRONIZOWANIA:
            wynik.append(p)
    return sorted(wynik, key=lambda p: p["sk"])


def pobierz_patch(klucz: str, uruchom=subprocess.run) -> str:
    w = uruchom(["aws", "s3", "cp", f"s3://{BUCKET}/{klucz}", "-", "--region", REGION], capture_output=True)
    if w.returncode != 0:
        raise BladStraznika(f"brak patcha {klucz} w S3: {(w.stderr or b'').decode('utf-8', 'replace')[-300:]}")
    return w.stdout.decode("utf-8")


def skrot_poprawek(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(ids).encode()).hexdigest()[:8]


def zastosuj(repo: Path, tag: str, uruchom=subprocess.run, pobierz=None) -> tuple[str, list[str], list[str]]:
    """Zwraca (nowy tag, zastosowane id, pominiete id). BladStraznika, gdy patch sie nie stosuje."""
    pobierz = pobierz or (lambda k: pobierz_patch(k, uruchom))
    zastosowane, pominiete = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for p in oczekujace(uruchom):
            plik = Path(tmp) / "p.patch"
            plik.write_text(pobierz(p["patch_klucz"]), encoding="utf-8")
            if uruchom(["git", "apply", "--check", "--reverse", str(plik)], cwd=repo,
                       capture_output=True).returncode == 0:
                pominiete.append(p["sk"])       # juz w tym kodzie (np. zapisana w master)
                continue
            w = uruchom(["git", "apply", "--3way", str(plik)], cwd=repo, capture_output=True, text=True)
            if w.returncode != 0:
                raise BladStraznika(f"poprawka {p['sk']} (blad {p.get('odcisk', '?')}) nie stosuje sie do master: "
                                    f"{(w.stderr or '')[-300:]}")
            zastosowane.append(p["sk"])
    if not zastosowane:
        return tag, [], pominiete
    uruchom(["git", "-c", "user.name=notarai-samonaprawa", "-c", "user.email=samonaprawa@notarai.pl",
             "commit", "-q", "-a", "-m", "Poprawki samonaprawy z produkcji (jeszcze nie w master): " + ", ".join(zastosowane)],
            cwd=repo, check=True, capture_output=True)
    return f"{tag}-sn{skrot_poprawek(zastosowane)}", zastosowane, pominiete


def powiadom(tresc: str, uruchom=subprocess.run) -> None:
    uruchom(["aws", "sns", "publish", "--topic-arn", TEMAT, "--region", REGION,
             "--subject", "notarai: wdrozenie wstrzymane - poprawka z produkcji sie nie stosuje",
             "--message", tresc], capture_output=True)


def main(argv: list[str] | None = None, uruchom=subprocess.run) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--zapisz-env")
    a = parser.parse_args(argv)
    try:
        tag, zastosowane, pominiete = zastosuj(Path(a.repo), a.tag, uruchom)
    except BladStraznika as e:
        tresc = (f"Zwykle wdrozenie z GitHuba zostalo ZATRZYMANE, bo poprawka wdrozona wczesniej przez samonaprawe "
                 f"nie pasuje do obecnego kodu w master i zostalaby nadpisana. Szczegoly: {e}. "
                 "Co zrobic: scal pull request samonaprawy (etykieta samonaprawa) albo rozwiaz konflikt recznie, "
                 "potem uruchom wdrozenie ponownie.")
        print(f"::error::{tresc}")
        powiadom(tresc, uruchom)
        return 1
    print(f"Poprawki samonaprawy: zastosowano {len(zastosowane)}, juz w kodzie {len(pominiete)}; tag {tag}")
    if a.zapisz_env:
        with open(a.zapisz_env, "a", encoding="utf-8") as f:
            f.write(f"TAG={tag}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
