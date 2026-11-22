"""Read-only ELI inspection CLI. Run: python -m tools.eli_source DU/2026/1243"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .eli_gate import EliAct, EliSourceError, _open_no_redirect, fetch_document, fetch_official_metadata, decide_source
from .quote_gate import match_literal_quote


def _read_quote(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise EliSourceError("quote file must be a bounded regular file")
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as exc:
        raise EliSourceError("quote file could not be decoded") from exc


def main(argv: list[str] | None = None, opener=_open_no_redirect) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("eli", help="Canonical ELI identifier, e.g. DU/2026/1243")
    parser.add_argument("--fetch-format", choices=("html", "pdf"),
                        help="Download the declared official representation in memory and print SHA-256 receipt")
    parser.add_argument("--quote-file", type=Path,
                        help="For HTML only: check a short literal quote from a local UTF-8 file")
    args = parser.parse_args(argv)
    try:
        act = EliAct.parse(args.eli)
        metadata = fetch_official_metadata(act, opener=opener)
        decision = decide_source(act, metadata)
        result = decision.as_dict()
        if args.quote_file and args.fetch_format != "html":
            raise EliSourceError("a literal quote requires --fetch-format html")
        if args.fetch_format:
            document = fetch_document(act, decision, args.fetch_format, opener=opener)
            result["document_receipt"] = document.receipt()
            if args.quote_file:
                result["quote_receipt"] = match_literal_quote(document, _read_quote(args.quote_file)).as_dict()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if not result.get("quote_receipt") or result["quote_receipt"]["matched_literal_in_published_document"] else 2
    except (EliSourceError, OSError) as exc:
        # Source bytes, documents and filesystem paths never enter error logs.
        reason = str(exc) if isinstance(exc, EliSourceError) else "local file I/O error"
        print("ELI source gate blocked: " + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())