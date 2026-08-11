from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from src.domain.models.daily import CandidateRegistry


class CandidateRegistryStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, *, data_origin: str) -> CandidateRegistry:
        if not self.path.exists():
            return CandidateRegistry(data_origin=data_origin)
        try:
            registry = CandidateRegistry.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            raise ValueError(f"invalid candidate registry: {self.path}") from exc
        if registry.data_origin != data_origin:
            raise ValueError(
                f"candidate registry origin {registry.data_origin} cannot accept {data_origin} data"
            )
        return registry

    def save(self, registry: CandidateRegistry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(registry.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
