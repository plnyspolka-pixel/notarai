"""A real Windows window filled through UI Automation: WinForms labels, text boxes, a list,
a checkbox and a button whose handler writes what the program received. Windows CI only."""
import json
import os
import subprocess
import time
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt" or os.environ.get("NOTARAI_V2_TEST_UIA") != "1",
                                reason="needs an interactive Windows desktop (NOTARAI_V2_TEST_UIA=1)")

SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
$out = $args[0]
$f = New-Object Windows.Forms.Form
$f.Text = 'NotarAI Test Rejestr'; $f.Width = 520; $f.Height = 360; $f.StartPosition = 'CenterScreen'
function Add-Label($text, $y) { $l = New-Object Windows.Forms.Label; $l.Text = $text; $l.Left = 10; $l.Top = $y; $l.Width = 150; $f.Controls.Add($l) }
Add-Label 'Nazwisko:' 20
$n = New-Object Windows.Forms.TextBox; $n.Left = 170; $n.Top = 20; $n.Width = 250; $f.Controls.Add($n)
Add-Label 'Numer repertorium' 60
$r = New-Object Windows.Forms.TextBox; $r.Left = 170; $r.Top = 60; $r.Width = 250; $f.Controls.Add($r)
Add-Label 'Rodzaj czynności' 100
$c = New-Object Windows.Forms.ComboBox; $c.Left = 170; $c.Top = 100; $c.Width = 250; $c.DropDownStyle = 'DropDownList'
[void]$c.Items.AddRange(@('Umowa sprzedaży', 'Darowizna', 'Pełnomocnictwo')); $f.Controls.Add($c)
$k = New-Object Windows.Forms.CheckBox; $k.Text = 'Wypis wydany'; $k.Left = 170; $k.Top = 140; $k.Width = 200; $f.Controls.Add($k)
$b = New-Object Windows.Forms.Button; $b.Text = 'Zapisz w rejestrze'; $b.Left = 170; $b.Top = 190; $b.Width = 160
$b.Add_Click({
  @{ nazwisko = $n.Text; repertorium = $r.Text; rodzaj = [string]$c.SelectedItem; wypis = $k.Checked } |
    ConvertTo-Json | Set-Content -LiteralPath $out -Encoding utf8
  $f.Text = 'NotarAI Test Rejestr - zapisano'
})
$f.Controls.Add($b)
[void]$f.ShowDialog()
"""


def step(pole, zrodlo=""):
    return SimpleNamespace(pole=pole, zrodlo=zrodlo, dlaczego="", akcja="")


def test_a_real_windows_program_is_filled_and_saved_after_approval(tmp_path):
    from worker.autofill import Autofill
    from worker.win_fill import Desktop

    script, out = tmp_path / "form.ps1", tmp_path / "saved.json"
    script.write_text(SCRIPT, encoding="utf-8-sig")
    process = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA",
                                "-File", str(script), str(out)])
    try:
        desktop = Desktop()
        deadline = time.monotonic() + 30
        while "NotarAI Test Rejestr" not in " ".join(desktop.windows()):
            assert time.monotonic() < deadline, "the test window did not appear"
            time.sleep(0.5)
        procedure = SimpleNamespace(nazwa="Rejestr czynności", rodzaj="program", adres="NotarAI Test Rejestr", kroki=[
            step("Nazwisko"), step("Numer repertorium"), step("Rodzaj czynności"), step("Wypis wydany"),
            step("Zapisz w rejestrze", "wyślij")])
        values = [{"value": "Kowalski"}, {"value": "A 123/2026"}, {"value": "darowizna"}, {"value": "tak"},
                  {"value": "kliknij"}]
        autofill = Autofill({"program": lambda: desktop})
        preview = autofill.fill(procedure, values, actor="local-admin", case="k")
        assert [(r["field"], r["state"]) for r in preview["report"]] == [
            ("Nazwisko", "filled"), ("Numer repertorium", "filled"), ("Rodzaj czynności", "filled"),
            ("Wypis wydany", "filled")], preview["report"]
        assert preview["send"] == "Zapisz w rejestrze" and not out.exists()
        sent = autofill.send(preview["token"], "local-admin", "program")
        deadline = time.monotonic() + 10
        while not out.exists():
            assert time.monotonic() < deadline, "the program did not save"
            time.sleep(0.2)
        saved = json.loads(out.read_text(encoding="utf-8-sig"))
        assert saved == {"nazwisko": "Kowalski", "repertorium": "A 123/2026", "rodzaj": "Darowizna", "wypis": True}
        assert sent["state"] == "sent"
    finally:
        process.kill()
