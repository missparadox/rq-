from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.evaluation import EvaluationDetail


class EvaluationStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def evaluation_dir(self, evaluation_id: str) -> Path:
        return self.root / evaluation_id

    def metadata_path(self, evaluation_id: str) -> Path:
        return self.evaluation_dir(evaluation_id) / "metadata.json"

    def create_evaluation(self, *, evaluation_id: str, filename: str, file_bytes: bytes) -> dict[str, Any]:
        directory = self.evaluation_dir(evaluation_id)
        directory.mkdir(parents=True, exist_ok=False)
        safe_filename = Path(filename).name
        original_file_path = directory / safe_filename
        original_file_path.write_bytes(file_bytes)
        metadata_path = self.metadata_path(evaluation_id)
        metadata = {
            "evaluation_id": evaluation_id,
            "status": "pending",
            "filename": safe_filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "directory": directory,
            "original_file_path": original_file_path,
            "metadata_path": metadata_path,
        }

    def read_metadata(self, evaluation_id: str) -> dict[str, Any]:
        return json.loads(self.metadata_path(evaluation_id).read_text(encoding="utf-8"))

    def read_original_file_bytes(self, evaluation_id: str) -> bytes:
        metadata = self.read_metadata(evaluation_id)
        original_file_path = self.evaluation_dir(evaluation_id) / metadata["filename"]
        return original_file_path.read_bytes()

    def update_metadata(self, evaluation_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        metadata = self.read_metadata(evaluation_id)
        metadata.update(patch)
        self.metadata_path(evaluation_id).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return metadata

    def read_detail(self, evaluation_id: str) -> EvaluationDetail:
        metadata = self.read_metadata(evaluation_id)
        report_markdown = None
        report_path = metadata.get("report_path")
        if report_path:
            path = Path(report_path)
            if path.exists():
                report_markdown = path.read_text(encoding="utf-8")
        return EvaluationDetail.model_validate(
            {
                "evaluation_id": metadata["evaluation_id"],
                "status": metadata["status"],
                "filename": metadata["filename"],
                "created_at": metadata["created_at"],
                "started_at": metadata.get("started_at"),
                "finished_at": metadata.get("finished_at"),
                "error_message": metadata.get("error_message"),
                "report_markdown": report_markdown,
                "token_budget_path": metadata.get("token_budget_path"),
                "token_budget_summary": metadata.get("token_budget_summary"),
            }
        )
