"""Szablon stalego adresu wyjsciowego (infra/notarai-egress.yaml): zabezpieczenia."""
import re
from pathlib import Path

SZABLON = (Path(__file__).parent / "infra" / "notarai-egress.yaml").read_text(encoding="utf-8")


def _zasob(nazwa):
    m = re.search(rf"^  {nazwa}:\n((?:    .*\n|\n)+)", SZABLON, re.M)
    assert m, nazwa
    return m.group(0)


def test_adres_eip_chroniony_przed_usunieciem():
    blok = _zasob("AdresWyjsciowy")
    assert "DeletionPolicy: Retain" in blok and "UpdateReplacePolicy: Retain" in blok


def test_brama_i_trasa_tylko_gdy_nat_wlaczony():
    assert "Condition: NatIstnieje" in _zasob("BramaNat")
    assert "Condition: NatIstnieje" in _zasob("TrasaPrzezNat")
    assert 'Default: "false"' in SZABLON  # domyslnie brama wylaczona (koszt)


def test_pomiar_wychodzi_tylko_po_https():
    blok = _zasob("GrupaPomiaru")
    assert "FromPort: 443, ToPort: 443" in blok and "SecurityGroupIngress" not in blok


def test_brak_identyfikatorow_ani_adresow_w_repozytorium():
    assert not re.search(r"\b(vpc|subnet|sg|eipalloc|eni)-[0-9a-f]{8,}", SZABLON)
    assert not re.search(r"\b\d{12}\b", SZABLON)
    ipv4 = [i for i in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", SZABLON)
            if not i.startswith(("172.31.", "0.0.0.0", "2026"))]
    assert not ipv4, ipv4


def test_konwencje_nazw_i_opisow():
    assert "—" not in SZABLON and "–" not in SZABLON  # bez pauz w opisach zasobow
    assert "eu-central-1" in SZABLON and "notarai-egress" in SZABLON
