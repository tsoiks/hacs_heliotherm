"""The translation files stay in sync with strings.json."""

from __future__ import annotations

import json
from pathlib import Path

COMPONENT_DIR = (
    Path(__file__).parent.parent / "custom_components" / "heliotherm"
)


def _keys(value: object, prefix: str = "") -> set[str]:
    out: set[str] = set()
    assert isinstance(value, dict)
    for key, item in value.items():
        if isinstance(item, dict):
            out |= _keys(item, f"{prefix}{key}.")
        else:
            out.add(f"{prefix}{key}")
    return out


def test_translations_match_strings() -> None:
    """Every language file carries exactly the keys strings.json defines."""
    strings = json.loads((COMPONENT_DIR / "strings.json").read_text())
    expected = _keys(strings)
    for language in ("en", "de"):
        translation = json.loads(
            (COMPONENT_DIR / "translations" / f"{language}.json").read_text()
        )
        assert _keys(translation) == expected, (
            f"{language}.json keys diverge from strings.json"
        )


def test_every_entity_has_a_name_in_every_language() -> None:
    """No entity can lose its display name by a missing translation."""
    strings = json.loads((COMPONENT_DIR / "strings.json").read_text())
    for platform in ("sensor", "binary_sensor"):
        expected = set(strings["entity"][platform])
        for language in ("en", "de"):
            translation = json.loads(
                (COMPONENT_DIR / "translations" / f"{language}.json").read_text()
            )
            assert expected <= set(translation["entity"][platform]), (
                f"{language}.json misses names for {platform}:"
                f" {expected - set(translation['entity'][platform])}"
            )
