"""Read explicit project configuration without executing project code."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from .models import MaxkompilatorError


def load_config(path: str | Path) -> dict[str, Any]:
    root = Path(path).expanduser().resolve()
    if root.is_file():
        root = root.parent
    config_path = root / "maxkompilator.toml"
    if not config_path.exists():
        return {}
    if not config_path.is_file() or config_path.stat().st_size > 1024 * 1024:
        raise MaxkompilatorError("Nieprawidłowy lub zbyt duży maxkompilator.toml.")
    try:
        with config_path.open("rb") as stream:
            config = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise MaxkompilatorError(f"Nie można odczytać maxkompilator.toml: {exc}") from exc
    for section in ("project", "build", "python"):
        if section in config and not isinstance(config[section], dict):
            raise MaxkompilatorError(f"Sekcja [{section}] musi być tabelą TOML.")
    for section, names in (("project", ("kind", "entry")), ("build", ("target", "format", "output"))):
        for name in names:
            value = config.get(section, {}).get(name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise MaxkompilatorError(f"{section}.{name} musi być niepustym tekstem.")
    return config
