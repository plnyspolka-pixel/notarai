"""First-run guide: steps checked against the real state, skippable, never in a device's way."""
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize
from worker.settings import load


def office(tmp_path, picker=None):
    home = tmp_path / "home"
    token = initialize(home)
    return TestClient(create_app(home, folder_picker=picker)), {"Authorization": "Bearer " + token}, home


def say(client, headers, text=None, **extra):
    return client.post("/v2/chat", headers=headers, json={"text": text or "", **extra}).json()["blocks"]


def words(blocks):
    return "\n".join(b.get("text", "") for b in blocks)


def labels(blocks):
    return [i["label"] for b in blocks if b["type"] == "buttons" for i in b["items"]]


def test_the_first_start_opens_with_step_one_and_moves_on_when_it_is_really_done(tmp_path):
    client, admin, home = office(tmp_path)
    hello = say(client, admin, hello=True)
    assert "Witaj w NotarAI" in words(hello) and "krok 1 z 11: Kod odzyskiwania sejfu" in words(hello)
    assert {"Utwórz kod odzyskiwania", "Pomiń ten krok", "Cała lista"} <= set(labels(hello))
    reply = say(client, admin, "kod odzyskiwania")
    assert "✓ Kod odzyskiwania sejfu." in words(reply) and "krok 2 z 11: Zalogowanie stanowiska" in words(reply)
    skipped = say(client, admin, "pomiń krok")
    assert "Pominąłem: Zalogowanie stanowiska" in words(skipped) and "krok 3 z 11" in words(skipped)
    reply = say(client, admin, "mowa we frankfurcie")
    assert "✓ Gdzie mają być dane." in words(reply) and "Kopia zapasowa" in words(reply)
    listing = words(say(client, admin, "przewodnik"))
    assert "✓ 1. Kod odzyskiwania sejfu" in listing and "○ 2. Zalogowanie stanowiska (pominięty)" in listing


def test_folders_come_from_the_windows_dialog_and_feed_style_learning(tmp_path):
    acts = tmp_path / "Akty"
    acts.mkdir()
    client, admin, home = office(tmp_path, picker=lambda: str(acts))
    assert say(client, admin, "wybierz folder aktów")[0] == {"type": "pick-folder", "purpose": "akty",
                                                            "label": "Wybierz folder z aktami…"}
    assert client.post("/v2/pick-folder", headers=admin, json={}).json() == {"path": str(acts)}
    reply = say(client, admin, f"folder aktów {acts}")
    says = [i["say"] for b in reply if b["type"] == "buttons" for i in b["items"]]
    assert load(home).acts_dir == str(acts) and f"naucz się stylu z {acts}" in says
    assert "Nie ma takiego folderu" in words(say(client, admin, "folder aktów Z:\\nie-ma"))
    assert "Przeszukuję " + str(acts) in words(say(client, admin, "naucz się stylu z folderu aktów"))


def test_no_dialog_off_windows_and_no_dialog_for_devices(tmp_path):
    client, admin, _ = office(tmp_path)
    import worker.api as api
    if api.windows_folder_picker is None:
        assert client.post("/v2/pick-folder", headers=admin, json={}).status_code == 501
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": "write"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    assert client.post("/v2/pick-folder", headers=phone, json={}).status_code == 403
    assert "Przewodnik" not in words(say(client, phone, hello=True))
    assert "Przewodnik pierwszego" not in words(say(client, phone, "przewodnik"))


def test_activities_are_shown_once_then_offered_as_automatic(tmp_path):
    client, admin, home = office(tmp_path)
    first = say(client, admin, "czynności")
    assert "+ Wniosek o wpis w księdze wieczystej (EKW)" in labels(first)
    reply = say(client, admin, "dodaj czynność Wniosek o wpis w księdze wieczystej (EKW)")
    assert "○ Wniosek o wpis w księdze wieczystej (EKW) — do pokazania raz" in words(reply)
    assert "Pokaż raz: Wniosek o wpis w księdze wieczystej (EKW)" in labels(reply)
    from worker.local_secrets import read_secret
    from worker.procedures import CASE, SUFFIX, slug
    from worker.vault import Vault
    Vault(home, read_secret(home, "vault.key")).put(
        None, 0, slug("Wniosek o wpis w księdze wieczystej (EKW)") + SUFFIX, b"{}", case=CASE)
    learned = say(client, admin, "czynności")
    assert "— program robi to sam" in words(learned)
    assert "Zrób: Wniosek o wpis w księdze wieczystej (EKW)" in labels(learned)
    say(client, admin, "usuń czynność Wniosek o wpis w księdze wieczystej (EKW)")
    assert "program robi to sam" not in words(say(client, admin, "czynności"))


def test_the_guide_ends_and_stays_out_of_the_way(tmp_path):
    client, admin, _ = office(tmp_path)
    for _ in range(11):
        say(client, admin, "pomiń krok")
    hello = say(client, admin, hello=True)
    assert "Przewodnik" not in words(hello) and "Stan stanowiska" in labels(hello)
    assert "Wróć do pominiętych" in labels(say(client, admin, "przewodnik"))
    assert "krok 1 z 11" in words(say(client, admin, "przewodnik od nowa"))
