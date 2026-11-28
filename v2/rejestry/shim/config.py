"""Zastępstwo serwerowego config.py V1 w funkcji AWS: ekw.py czyta stąd tylko katalog spraw,
a funkcja niczego nie zapisuje (tylko /tmp, które znika z kontenerem)."""
from pathlib import Path

SPRAWY = Path("/tmp/sprawy")
