from __future__ import annotations

import importlib
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

def configure_runtime_env(
    monkeypatch,
    *,
    data_dir: str | None = None,
    openai_api_key: str | None = None,
    zhipu_api_key: str | None = None,
    debug_fallback_enabled: bool = False,
) -> None:
    if data_dir is None:
        monkeypatch.delenv("REQUIREMENTS_EVALUATOR_DATA_DIR", raising=False)
    else:
        monkeypatch.setenv("REQUIREMENTS_EVALUATOR_DATA_DIR", data_dir)

    if openai_api_key is None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("OPENAI_API_KEY", openai_api_key)

    if zhipu_api_key is None:
        monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ZHIPU_API_KEY", zhipu_api_key)

    if debug_fallback_enabled:
        monkeypatch.setenv("REQUIREMENTS_EVALUATOR_DEBUG_FALLBACK", "1")
    else:
        monkeypatch.delenv("REQUIREMENTS_EVALUATOR_DEBUG_FALLBACK", raising=False)

    monkeypatch.setenv("PATH", "")


def import_app_main_module():
    sys.modules.pop("app.main", None)
    importlib.invalidate_caches()
    return importlib.import_module("app.main")
