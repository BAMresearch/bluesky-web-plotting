from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .config import RootConfig
from .predicates import ConfigError


def load_config(path: Path) -> RootConfig:
    """
    Load, parse, and validate timeline config from a JSON file.

    Raises
    ------
    ConfigError
        If JSON is invalid or the config fails validation.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ConfigError(f"config file read failed: {path}: {e}") from e

    try:
        data: Any = json.loads(raw_text)
    except json.JSONDecodeError as e:
        # include line/col for easy debugging
        raise ConfigError(f"invalid JSON in {path} at line {e.lineno}, col {e.colno}: {e.msg}") from e

    if not isinstance(data, Mapping):
        raise ConfigError("root: config must be a JSON object")

    return RootConfig.from_dict(data, path="root")