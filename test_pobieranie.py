"""Regresje dla działu pobierania NotarAI."""
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from scripts.buduj_pobieranie import BROWSER_FILES, OPENOFFICE_FILES, ROOT, build


class TestPobieranie(unittest.TestCase):
    def test_all_four_real_downloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            hashes = build(output)
            self.assertEqual(len(hashes), 4)
            for name in hashes:
                self.assertTrue((output / name).is_file(), name)
            with ZipFile(output / "notarai-chrome.zip") as f:
                self.assertEqual(set(f.namelist()), set(BROWSER_FILES))
                manifest = json.loads(f.read("manifest.json"))
                self.assertEqual(manifest["manifest_version"], 3)
                self.assertNotIn("debugger", manifest.get("permissions", []))
            self.assertEqual(
                (output / "notarai-chrome.zip").read_bytes(),
                (output / "notarai-edge.zip").read_bytes(),
            )
            with ZipFile(output / "notarai-openoffice.oxt") as f:
                self.assertEqual(set(f.namelist()), set(OPENOFFICE_FILES))
                ET.fromstring(f.read("META-INF/manifest.xml"))
                ET.fromstring(f.read("Addons.xcu"))
                ET.fromstring(f.read("description.xml"))
                self.assertNotIn("read_bytes(", f.read("package/notarai.py").decode("utf-8"))
            ET.parse(output / "notarai-word.xml")
            sums = (output / "SHA256SUMS.txt").read_text(encoding="utf-8")
            for name in hashes:
                self.assertIn(f"{hashes[name]}  {name}", sums)

    def test_site_exposes_downloads_and_not_windows_exe(self):
        html = (ROOT / "strona" / "do-pobrania" / "index.html").read_text(encoding="utf-8")
        for name in ("notarai-word.xml", "notarai-openoffice.oxt", "notarai-chrome.zip", "notarai-edge.zip"):
            self.assertIn('href="pliki/' + name + '"', html)
        self.assertNotIn('href="pliki/notarai-pomocnik.exe"', html)
        panel = (ROOT / "strona" / "do-pobrania" / "word" / "panel.html").read_text(encoding="utf-8")
        self.assertIn("Word.run", panel)
        self.assertNotIn("fetch(", panel)


if __name__ == "__main__":
    unittest.main()