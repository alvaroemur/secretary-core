"""Legacy path keys resolve through their canonical form once the instance drops its aliases."""

from pathlib import Path

import pytest

from secretary import config

CANONICAL_ONLY = {
    "paths": {
        "extractors": {
            "mail": {"memory": "extractors/mail/memory"},
            "whatsapp": {"review_config": "extractors/whatsapp/local-review.yaml"},
        },
        "loops": {"job_search": {"state": "loops/job-search/state.md"}},
        "subsystem": {"heartbeat": "subsystem/heartbeat"},
        "operational": {"skills_vs_operational": "canon/operational/skills-vs-operational.md"},
        "knowledge": {"catalog": "knowledge/catalog"},
        "rules": "canon/rules",
        "wiki": {"articles": "knowledge/wiki/articulos"},
    }
}


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRETARY_INSTANCE", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    "legacy, rel",
    [
        ("mail.memory", "extractors/mail/memory"),
        ("whatsapp.review_config", "extractors/whatsapp/local-review.yaml"),
        ("job_search.state", "loops/job-search/state.md"),
        ("operations.heartbeat", "subsystem/heartbeat"),
        ("extractores.mail.memory", "extractors/mail/memory"),
        ("extractores.job_search.state", "loops/job-search/state.md"),
        ("memoria.catalog", "knowledge/catalog"),
        ("doctrines", "canon/rules"),
        ("policies.skills_vs_policies", "canon/operational/skills-vs-operational.md"),
    ],
)
def test_legacy_key_resolves_to_canonical(instance: Path, legacy: str, rel: str) -> None:
    assert config.resolve_path_key(legacy, CANONICAL_ONLY) == (instance / rel).resolve()


def test_key_present_in_config_wins(instance: Path) -> None:
    cfg = {"paths": {**CANONICAL_ONLY["paths"], "mail": {"memory": "legacy/mail"}}}
    assert config.resolve_path_key("mail.memory", cfg) == (instance / "legacy/mail").resolve()


def test_non_legacy_key_is_untouched(instance: Path) -> None:
    assert config.resolve_path_key("wiki.articles", CANONICAL_ONLY) == (
        instance / "knowledge/wiki/articulos"
    ).resolve()


def test_unknown_key_still_fails(instance: Path) -> None:
    with pytest.raises(KeyError):
        config.resolve_path_key("mail.nope", CANONICAL_ONLY)
