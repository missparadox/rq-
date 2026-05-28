import hashlib
import subprocess
from pathlib import Path


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(payload: str) -> str:
    return sha256_bytes(payload.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def detect_app_version(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "dev"
    if result.returncode != 0:
        return "dev"
    return result.stdout.strip() or "dev"


def build_dedupe_key(
    *,
    input_fingerprint: str,
    skill_version: str,
    report_template_version: str,
    model_name: str,
    model_provider: str,
    app_version: str,
) -> str:
    material = "|".join(
        [
            input_fingerprint,
            skill_version,
            report_template_version,
            model_name,
            model_provider,
            app_version,
        ]
    )
    return sha256_text(material)
