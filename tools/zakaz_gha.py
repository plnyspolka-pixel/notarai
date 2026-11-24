"""Twarda reguła właściciela (23.11.2026): ŻADNEGO renderu na GitHub Actions.

Wywołaj `zakaz_renderu_na_github_actions("co")` na starcie każdej ścieżki, która
renderuje (scenografia Blender, fabryka odcinków, montaż, głos). Rendery idą tylko
przez Cloudflare (finyou-render). Workflow pilnuje tools/zakaz_renderu_gha.py.
"""
from __future__ import annotations

import os
from typing import Mapping


class RenderNaGitHubActions(RuntimeError):
    pass


def zakaz_renderu_na_github_actions(co: str, env: Mapping[str, str] | None = None) -> None:
    env = os.environ if env is None else env
    if env.get("GITHUB_ACTIONS") == "true" or env.get("GITHUB_WORKFLOW"):
        raise RenderNaGitHubActions(
            f"ZAKAZ: {co} nie może działać na GitHub Actions. Renderuj przez Cloudflare (finyou-render)."
        )
