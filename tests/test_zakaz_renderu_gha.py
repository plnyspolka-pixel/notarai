import importlib.util
import pathlib

import pytest

from tools.zakaz_gha import RenderNaGitHubActions, zakaz_renderu_na_github_actions

KORZEN = pathlib.Path(__file__).resolve().parents[1]


def _straznik():
    spec = importlib.util.spec_from_file_location("zakaz", KORZEN / "tools" / "zakaz_renderu_gha.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_runtime_blokuje_na_gha():
    with pytest.raises(RenderNaGitHubActions):
        zakaz_renderu_na_github_actions("x", {"GITHUB_ACTIONS": "true"})
    zakaz_renderu_na_github_actions("x", {})


def test_zaden_workflow_nie_renderuje():
    m = _straznik()
    m.samotest()
    assert m.sprawdz_repo(KORZEN) == []
