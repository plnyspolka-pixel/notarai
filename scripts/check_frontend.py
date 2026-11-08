"""Sprawdzenie składni JavaScript w skryptach osadzonych w HTML.

Nie uruchamia przeglądarki, nie wysyła żądań sieciowych i nie przetwarza
rzeczywistych aktów ani danych kancelarii.
"""
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = (
    "static/index.html",
    "static/admin.html",
    "static/rejestracja.html",
    "strona/index.html",
)


class InlineScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self._script = None

    def handle_starttag(self, tag, attrs):
        if tag != "script":
            return
        options = dict(attrs)
        if "src" in options or options.get("type", "").lower() not in ("", "text/javascript", "module"):
            self._script = None
            return
        self._script = []

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.scripts.append("".join(self._script))
            self._script = None


def main():
    tested = 0
    with tempfile.TemporaryDirectory(prefix="notarai-js-") as folder:
        for relative in HTML_FILES:
            page = ROOT / relative
            parser = InlineScripts()
            parser.feed(page.read_text(encoding="utf-8-sig"))
            for number, script in enumerate(parser.scripts, 1):
                if not script.strip():
                    continue
                source = Path(folder) / f"{page.stem}-{number}.js"
                source.write_text(script, encoding="utf-8")
                result = subprocess.run(
                    ["node", "--check", str(source)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode:
                    raise SystemExit(
                        f"Blad JavaScript w {relative}, skrypt {number}:\n{result.stderr}"
                    )
                tested += 1
    print(f"Poprawna skladnia {tested} osadzonych skryptow JavaScript.")


if __name__ == "__main__":
    main()
