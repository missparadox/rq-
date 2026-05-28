from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from app.core.paths import REPO_ROOT


def _env_or_none(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return value


def _env_or_default(name: str, default: str) -> str:
    value = _env_or_none(name)
    return default if value is None else value


def _debug_fallback_enabled() -> bool:
    return os.environ.get("REQUIREMENTS_EVALUATOR_DEBUG_FALLBACK") == "1"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    openai_api_key: str | None
    openai_model: str
    openai_base_url: str
    zhipu_api_key: str | None
    zhipu_model: str
    zhipu_base_url: str
    codex_model: str
    debug_fallback_enabled: bool


def get_settings() -> Settings:
    data_dir = Path(_env_or_default("REQUIREMENTS_EVALUATOR_DATA_DIR", str(REPO_ROOT / "data")))
    return Settings(
        data_dir=data_dir,
        openai_api_key=_env_or_none("OPENAI_API_KEY"),
        openai_model=_env_or_default("OPENAI_MODEL", "gpt-5.4"),
        openai_base_url=_env_or_default("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        zhipu_api_key=_env_or_none("ZHIPU_API_KEY"),
        zhipu_model=_env_or_default("ZHIPU_MODEL", "glm-5"),
        zhipu_base_url=_env_or_default("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        codex_model=_env_or_default("CODEX_MODEL", "gpt-5.4"),
        debug_fallback_enabled=_debug_fallback_enabled(),
    )
