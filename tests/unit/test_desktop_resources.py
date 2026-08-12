from __future__ import annotations

from pathlib import Path

from src.desktop import resources


def test_development_resources_resolve_to_repository(monkeypatch) -> None:
    monkeypatch.delattr(resources.sys, "_MEIPASS", raising=False)
    monkeypatch.delattr(resources.sys, "frozen", raising=False)
    assert resources.default_verified_urls_path().name == "verified-urls.json"
    assert resources.default_verified_urls_path().parent == Path(__file__).parents[2]
    assert resources.default_output_path("output") == Path("output")


def test_frozen_relative_output_uses_user_documents(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(resources.sys, "frozen", True, raising=False)
    monkeypatch.setattr(resources.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(resources.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    assert resources.default_verified_urls_path() == tmp_path / "verified-urls.json"
    assert resources.default_output_path("output") == (
        tmp_path / "home" / "Documents" / "IdeaDiscoveryGraph" / "output"
    )
