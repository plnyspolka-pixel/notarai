"""Deterministic notarial rules shared with V1 (code only, never V1 data or configuration).

V1's fee engine is a pure module with no I/O. V2 loads that single file instead of
keeping a second copy of the tariff. The installer bundles it under worker/_v1.
"""
import importlib.util
from functools import lru_cache
from pathlib import Path

_HERE = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def _load(name: str):
    for candidate in (_HERE / "_v1" / f"{name}.py", _HERE.parents[1] / f"{name}.py"):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location(f"notarai_v1_{name}", candidate)
            module = importlib.util.module_from_spec(spec)
            import sys
            sys.modules[spec.name] = module          # dataclasses in a module look themselves up here
            spec.loader.exec_module(module)
            return module
    raise RuntimeError(f"shared module {name} is not installed")


def fee_estimate(parameters: dict) -> dict:
    """Maximum notarial fee and related costs. The code computes; a model never does."""
    return _load("taksa").oblicz(parameters)


def fee_catalog() -> dict:
    return _load("taksa").katalog()


def amount_in_words(text: str) -> str:
    return _load("slownie").slownie_kwoty(text)


def krz_portal():
    """V1's knowledge of the debtors' register portal (tabs, recognition patterns, the Playwright adapter)."""
    return _load("krz_portal")


def valid_land_register(number: str) -> tuple[bool, str]:
    return _load("walidacja").ksiega_wieczysta(number)


def valid_pesel(number: str) -> tuple[bool, str]:
    return _load("walidacja").pesel(number)
