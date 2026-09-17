"""Usuwa wpis login_session z profilu [default] w ~/.aws/config.

Po zapisaniu stalych kluczy uzytkownika IAM ten wpis jest zbedny, a jego
obecnosc sprawia, ze AWS CLI nadal probuje sesji root z "aws login".
Reszta pliku zostaje bez zmian. Plik credentials nie jest ruszany.
"""
from pathlib import Path

config = Path.home() / ".aws" / "config"
if not config.exists():
    print("brak ~/.aws/config, nic do zrobienia")
    raise SystemExit(0)

linie = config.read_text(encoding="utf-8").splitlines(keepends=True)
wynik, w_default, usuniete = [], False, 0
for linia in linie:
    if linia.strip().startswith("["):
        w_default = linia.strip() == "[default]"
    if w_default and linia.strip().lower().startswith("login_session"):
        usuniete += 1
        continue
    wynik.append(linia)

if usuniete:
    config.with_suffix(".bak").write_text("".join(linie), encoding="utf-8")
    config.write_text("".join(wynik), encoding="utf-8")
print(f"usunieto wpisow login_session: {usuniete} (kopia: config.bak)" if usuniete else "login_session nie bylo")
