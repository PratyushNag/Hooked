from __future__ import annotations

from pathlib import Path

import yaml

from app.config.schema import HookedConfig


def load_config_file(path: str | Path) -> HookedConfig:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found: {file_path}")

    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    return HookedConfig.model_validate(data)
