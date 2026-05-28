from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.clients.model_client import resolve_model_runtime
from app.core.config import get_settings
from app.core.paths import REPO_ROOT, REPORT_TEMPLATE_FILE, SKILL_FILE
from app.core.versioning import build_dedupe_key, detect_app_version, sha256_bytes, sha256_file
from app.models.evaluation import EvaluationDetail


@dataclass
class CreateEvaluationResult:
    evaluation_id: str
    status: str
    filename: str
    dedupe_hit: bool
    created_at: str


class EvaluationService:
    def __init__(self, store) -> None:
        self.store = store
        settings = get_settings()
        runtime = resolve_model_runtime(settings)
        self.model_name = runtime.model_name
        self.model_provider = runtime.provider_name
        self.skill_version = sha256_file(SKILL_FILE)
        self.report_template_version = sha256_file(REPORT_TEMPLATE_FILE)
        self.app_version = detect_app_version(REPO_ROOT)

    def create_or_reuse(self, *, filename: str, file_bytes: bytes) -> CreateEvaluationResult:
        input_fingerprint = sha256_bytes(file_bytes)
        dedupe_key = build_dedupe_key(
            input_fingerprint=input_fingerprint,
            skill_version=self.skill_version,
            report_template_version=self.report_template_version,
            model_name=self.model_name,
            model_provider=self.model_provider,
            app_version=self.app_version,
        )
        reusable_metadata = self._find_reusable_metadata(dedupe_key)
        if reusable_metadata is not None:
            return CreateEvaluationResult(
                evaluation_id=reusable_metadata["evaluation_id"],
                status=reusable_metadata["status"],
                filename=reusable_metadata["filename"],
                dedupe_hit=True,
                created_at=reusable_metadata["created_at"],
            )

        evaluation_id = f"eval_{uuid4().hex}"
        self.store.create_evaluation(
            evaluation_id=evaluation_id,
            filename=filename,
            file_bytes=file_bytes,
        )
        metadata = self.store.update_metadata(
            evaluation_id,
            {
                "input_fingerprint": input_fingerprint,
                "skill_version": self.skill_version,
                "report_template_version": self.report_template_version,
                "model_name": self.model_name,
                "model_provider": self.model_provider,
                "app_version": self.app_version,
                "dedupe_key": dedupe_key,
            },
        )
        return CreateEvaluationResult(
            evaluation_id=evaluation_id,
            status=metadata["status"],
            filename=metadata["filename"],
            dedupe_hit=False,
            created_at=metadata["created_at"],
        )

    def _find_reusable_metadata(self, dedupe_key: str) -> dict[str, str] | None:
        for evaluation_dir in self.store.root.iterdir():
            if not evaluation_dir.is_dir():
                continue
            metadata_path = self.store.metadata_path(evaluation_dir.name)
            if not metadata_path.exists():
                continue
            metadata = self.store.read_metadata(evaluation_dir.name)
            if metadata.get("dedupe_key") != dedupe_key:
                continue
            if metadata.get("status") == "failed":
                continue
            return metadata
        return None

    def get_detail(self, evaluation_id: str) -> EvaluationDetail:
        return self.store.read_detail(evaluation_id)

    def retry(self, evaluation_id: str) -> CreateEvaluationResult:
        metadata = self.store.read_metadata(evaluation_id)
        if metadata.get("status") != "failed":
            raise ValueError("Only failed evaluations can be retried.")
        file_bytes = self.store.read_original_file_bytes(evaluation_id)
        return self.create_or_reuse(filename=metadata["filename"], file_bytes=file_bytes)
